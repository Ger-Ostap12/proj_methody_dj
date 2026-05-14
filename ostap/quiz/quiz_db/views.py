"""HTTP-представления домена тестов (модели в ``quiz_db.models``)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import AnswerOption, Question, QuestionType, Quiz, QuizAttempt, StudentAnswer


def _attempts_used(*, user, quiz: Quiz) -> int:
    return QuizAttempt.objects.filter(student=user, quiz=quiz).count()


def _deadline(attempt: QuizAttempt):
    return attempt.started_at + timedelta(minutes=attempt.quiz.time_limit_minutes)


def _correct_option_ids(question: Question) -> set[int]:
    return set(
        AnswerOption.objects.filter(question=question, is_correct=True).values_list('pk', flat=True)
    )


def _parse_selected_ids_for_question(request: HttpRequest, question: Question) -> set[int]:
    key = f'answer_{question.pk}'
    if question.question_type == QuestionType.SINGLE:
        v = request.POST.get(key)
        if not v:
            return set()
        try:
            return {int(v)}
        except (TypeError, ValueError):
            return set()
    ids: set[int] = set()
    for item in request.POST.getlist(key):
        try:
            ids.add(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _options_belong_to_question(question: Question, option_ids: set[int]) -> bool:
    if not option_ids:
        return True
    cnt = AnswerOption.objects.filter(question=question, pk__in=option_ids).count()
    return cnt == len(option_ids)


def _score_attempt(*, attempt: QuizAttempt) -> tuple[int, int]:
    questions = list(attempt.quiz.questions.all())
    max_score = len(questions)
    score = 0
    for q in questions:
        correct = _correct_option_ids(q)
        sa = StudentAnswer.objects.filter(attempt=attempt, question=q).first()
        selected: set[int] = set()
        if sa is not None:
            selected = set(sa.selected_options.values_list('pk', flat=True))
        if selected == correct:
            score += 1
    return score, max_score


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    quizzes = (
        Quiz.objects.filter(is_published=True)
        .select_related('author')
        .annotate(question_count=Count('questions'))
    )
    return render(
        request,
        'quiz_db/home.html',
        {'quizzes': quizzes},
    )


@require_GET
def quiz_detail(request: HttpRequest, pk: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=pk, is_published=True)
    used = _attempts_used(user=request.user, quiz=quiz) if request.user.is_authenticated else 0
    can_start = request.user.is_authenticated and used < quiz.max_attempts
    return render(
        request,
        'quiz_db/quiz_detail.html',
        {
            'quiz': quiz,
            'attempts_used': used,
            'can_start': can_start,
        },
    )


@login_required
@require_POST
def quiz_start(request: HttpRequest, pk: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=pk, is_published=True)
    if _attempts_used(user=request.user, quiz=quiz) >= quiz.max_attempts:
        messages.error(request, 'Достигнут лимит попыток для этого теста.')
        return redirect('quiz_detail', pk=quiz.pk)

    q_count = quiz.questions.count()
    attempt = QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        started_at=timezone.now(),
        submitted_at=None,
        score=0,
        max_score=q_count,
    )
    return redirect('attempt_take', attempt_id=attempt.pk)


@login_required
@require_http_methods(['GET', 'HEAD'])
def attempt_take(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz'),
        pk=attempt_id,
        student=request.user,
    )
    if attempt.is_submitted:
        return redirect('attempt_result', attempt_id=attempt.pk)

    questions = list(
        attempt.quiz.questions.order_by('order', 'pk').prefetch_related(
            Prefetch('answer_options', queryset=AnswerOption.objects.order_by('order', 'pk'))
        )
    )
    deadline = _deadline(attempt)
    return render(
        request,
        'quiz_db/attempt_take.html',
        {
            'attempt': attempt,
            'questions': questions,
            'deadline_iso': deadline.isoformat(),
            'overdue': timezone.now() > deadline,
        },
    )


@login_required
@require_POST
def attempt_submit(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz').prefetch_related('quiz__questions'),
        pk=attempt_id,
        student=request.user,
    )
    if attempt.is_submitted:
        messages.info(request, 'Эта попытка уже отправлена.')
        return redirect('attempt_result', attempt_id=attempt.pk)

    questions = list(attempt.quiz.questions.order_by('order', 'pk'))
    now = timezone.now()
    deadline = _deadline(attempt)

    for q in questions:
        selected = _parse_selected_ids_for_question(request, q)
        if q.question_type == QuestionType.SINGLE and len(selected) > 1:
            return HttpResponseBadRequest('Неверный формат ответа: ожидается один вариант.')
        if not _options_belong_to_question(q, selected):
            return HttpResponseBadRequest('Выбраны варианты, не относящиеся к вопросу.')

    with transaction.atomic():
        locked = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.submitted_at is not None:
            return redirect('attempt_result', attempt_id=locked.pk)

        for q in questions:
            selected = _parse_selected_ids_for_question(request, q)
            sa, _created = StudentAnswer.objects.get_or_create(attempt=locked, question=q)
            sa.selected_options.set(list(selected))

        score, max_score = _score_attempt(attempt=locked)
        locked.score = score
        locked.max_score = max_score
        locked.submitted_at = now
        locked.save(update_fields=['score', 'max_score', 'submitted_at'])

    if now > deadline:
        messages.warning(
            request,
            'Отправка выполнена после лимита времени; результат всё равно засчитан.',
        )

    messages.success(request, 'Ответы сохранены.')
    return redirect('attempt_result', attempt_id=attempt.pk)


@login_required
@require_GET
def attempt_result(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz'),
        pk=attempt_id,
        student=request.user,
    )
    return render(
        request,
        'quiz_db/attempt_result.html',
        {'attempt': attempt},
    )
