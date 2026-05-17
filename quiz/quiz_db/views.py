"""
HTTP-представления quiz_db.

Модели: ``proj_methody_dj-vorovsky/quiz/quiz_db/models.py`` (тот же app при сборке).
Шаблоны anasteysha: index, quiz_list, quiz_detail, result, profile, edit_profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import AnswerOption, Question, QuestionType, Quiz, QuizAttempt, StudentAnswer

_DIFFICULTY_LABELS = {
    'beginner': 'Начальный',
    'intermediate': 'Средний',
    'advanced': 'Сложный',
}


@dataclass
class TestCard:
    """Объект для шаблонов anasteysha (поле test.*)."""

    id: int
    name: str
    description: str
    questions_count: int
    difficulty: str
    color: str
    is_favorite: bool

    def get_difficulty_display(self) -> str:
        return _DIFFICULTY_LABELS.get(self.difficulty, self.difficulty)


def _favorite_ids(request: HttpRequest) -> set[int]:
    raw = request.session.get('favorite_quiz_ids', [])
    return {int(x) for x in raw}


def _set_favorite(request: HttpRequest, quiz_id: int, *, add: bool) -> None:
    ids = _favorite_ids(request)
    if add:
        ids.add(quiz_id)
    else:
        ids.discard(quiz_id)
    request.session['favorite_quiz_ids'] = sorted(ids)


def _published_quizzes():
    return (
        Quiz.objects.filter(is_published=True)
        .select_related('author')
        .annotate(questions_count=Count('questions'))
    )


def _as_test_card(quiz: Quiz, request: HttpRequest) -> TestCard:
    return TestCard(
        id=quiz.pk,
        name=quiz.title,
        description=quiz.description,
        questions_count=getattr(quiz, 'questions_count', quiz.questions.count()),
        difficulty='intermediate',
        color='info',
        is_favorite=quiz.pk in _favorite_ids(request),
    )


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
        v = request.POST.get(key) or request.POST.get('answer')
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


def _ordered_questions(quiz: Quiz) -> list[Question]:
    return list(quiz.questions.order_by('order', 'pk'))


def _active_attempt(user, quiz: Quiz) -> QuizAttempt | None:
    return (
        QuizAttempt.objects.filter(student=user, quiz=quiz, submitted_at__isnull=True)
        .order_by('-started_at')
        .first()
    )


def _get_or_create_attempt(user, quiz: Quiz) -> QuizAttempt:
    attempt = _active_attempt(user, quiz)
    if attempt:
        return attempt
    if _attempts_used(user=user, quiz=quiz) >= quiz.max_attempts:
        raise PermissionError('limit')
    q_count = quiz.questions.count()
    return QuizAttempt.objects.create(
        student=user,
        quiz=quiz,
        started_at=timezone.now(),
        submitted_at=None,
        score=0,
        max_score=q_count,
    )


def _finalize_attempt(attempt: QuizAttempt) -> QuizAttempt:
    score, max_score = _score_attempt(attempt=attempt)
    attempt.score = score
    attempt.max_score = max_score
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=['score', 'max_score', 'submitted_at'])
    return attempt


# --- Главная / каталог (index.html, quiz_list.html) ---------------------------------


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    tests = [_as_test_card(q, request) for q in _published_quizzes()]
    return render(request, 'index.html', {'tests': tests})


@require_GET
def quiz_list(request: HttpRequest) -> HttpResponse:
    qs = _published_quizzes()
    search = (request.GET.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    difficulty = request.GET.get('difficulty')
    tests = [_as_test_card(q, request) for q in qs]
    return render(
        request,
        'quiz_list.html',
        {
            'tests': tests,
            'search_query': search,
            'difficulty': difficulty,
        },
    )


@login_required
@require_POST
def toggle_favorite(request: HttpRequest, test_id: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=test_id, is_published=True)
    fav = quiz.pk in _favorite_ids(request)
    _set_favorite(request, quiz.pk, add=not fav)
    return redirect(request.META.get('HTTP_REFERER') or 'quiz_list')


# --- Карточка теста / пошаговое прохождение (quiz_detail.html) ---------------------


@require_GET
def quiz_detail(request: HttpRequest, quiz_id: int) -> HttpResponse:
    """Без ?q — страница старта; с ?q — текущий вопрос (anasteysha)."""
    if request.GET.get('q'):
        return quiz_play(request, quiz_id)
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    used = _attempts_used(user=request.user, quiz=quiz) if request.user.is_authenticated else 0
    can_start = request.user.is_authenticated and used < quiz.max_attempts
    return render(
        request,
        'quiz_db/quiz_detail.html',
        {'quiz': quiz, 'attempts_used': used, 'can_start': can_start},
    )


@login_required
@require_GET
def quiz_play(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    questions = _ordered_questions(quiz)
    if not questions:
        messages.warning(request, 'В тесте пока нет вопросов.')
        return redirect('quiz_detail', quiz_id=quiz.pk)

    try:
        q_index = max(1, int(request.GET.get('q', 1)))
    except (TypeError, ValueError):
        q_index = 1
    q_index = min(q_index, len(questions))

    try:
        attempt = _get_or_create_attempt(request.user, quiz)
    except PermissionError:
        messages.error(request, 'Достигнут лимит попыток для этого теста.')
        return redirect('quiz_detail', quiz_id=quiz.pk)

    question = questions[q_index - 1]
    options = list(
        question.answer_options.order_by('order', 'pk').values('id', 'text')
    )
    return render(
        request,
        'quiz_detail.html',
        {
            'quiz_id': quiz.pk,
            'quiz_title': quiz.title,
            'current_question': q_index,
            'total_questions': len(questions),
            'question_text': question.text,
            'options': options,
            'attempt_id': attempt.pk,
        },
    )


@login_required
@require_POST
def submit_answer(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    questions = _ordered_questions(quiz)
    active = _active_attempt(request.user, quiz)
    if not active:
        messages.error(request, 'Сначала начните прохождение теста.')
        return redirect('quiz_detail', quiz_id=quiz.pk)
    attempt = get_object_or_404(
        QuizAttempt,
        pk=active.pk,
        student=request.user,
        quiz=quiz,
        submitted_at__isnull=True,
    )

    q_raw = request.POST.get('q') or request.GET.get('q', 1)
    try:
        q_index = max(1, int(q_raw))
    except (TypeError, ValueError):
        q_index = 1

    if q_index > len(questions):
        return redirect('quiz_result', quiz_id=quiz.pk)

    question = questions[q_index - 1]
    selected = _parse_selected_ids_for_question(request, question)

    if not _options_belong_to_question(question, selected):
        return HttpResponseBadRequest('Некорректный вариант ответа.')

    sa, _ = StudentAnswer.objects.get_or_create(attempt=attempt, question=question)
    sa.selected_options.set(list(selected))

    if q_index >= len(questions):
        _finalize_attempt(attempt)
        return redirect('quiz_result', quiz_id=quiz.pk)
    return redirect(f'/quiz/{quiz.pk}/?q={q_index + 1}')


@login_required
@require_GET
def quiz_result(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    attempt = (
        QuizAttempt.objects.filter(student=request.user, quiz=quiz, submitted_at__isnull=False)
        .order_by('-submitted_at')
        .first()
    )
    if not attempt:
        return redirect('quiz_detail', quiz_id=quiz.pk)

    total = attempt.max_score or 1
    correct = attempt.score
    score_percent = round(100 * correct / total) if total else 0
    mistakes = _build_mistakes(attempt)

    return render(
        request,
        'result.html',
        {
            'quiz_id': quiz.pk,
            'score_percent': score_percent,
            'correct_answers': correct,
            'total_questions': total,
            'mistakes': mistakes,
        },
    )


def _build_mistakes(attempt: QuizAttempt) -> list[dict[str, Any]]:
    mistakes: list[dict[str, Any]] = []
    for q in attempt.quiz.questions.order_by('order', 'pk'):
        correct = AnswerOption.objects.filter(question=q, is_correct=True)
        sa = StudentAnswer.objects.filter(attempt=attempt, question=q).first()
        selected = set()
        if sa:
            selected = set(sa.selected_options.values_list('pk', flat=True))
        correct_ids = set(correct.values_list('pk', flat=True))
        if selected == correct_ids:
            continue
        user_text = ', '.join(
            AnswerOption.objects.filter(pk__in=selected).values_list('text', flat=True)
        ) or '—'
        correct_text = ', '.join(correct.values_list('text', flat=True))
        mistakes.append(
            {
                'question': q.text,
                'user_answer': user_text,
                'correct_answer': correct_text,
            }
        )
    return mistakes


# --- Профиль (profile.html, edit_profile.html) ------------------------------------


@login_required
@require_GET
def profile(request: HttpRequest) -> HttpResponse:
    attempts = (
        QuizAttempt.objects.filter(student=request.user, submitted_at__isnull=False)
        .select_related('quiz')
        .order_by('-submitted_at')[:50]
    )
    test_history = []
    percents: list[int] = []
    for a in attempts:
        total = a.max_score or 1
        pct = round(100 * a.score / total)
        percents.append(pct)
        test_history.append(
            {
                'test_name': a.quiz.title,
                'completed_at': a.submitted_at,
                'score_percent': pct,
                'correct': a.score,
                'total': a.max_score,
            }
        )
    avg = round(sum(percents) / len(percents)) if percents else 0
    return render(
        request,
        'profile.html',
        {
            'total_tests_passed': len(test_history),
            'average_score': avg,
            'best_score': max(percents) if percents else 0,
            'test_history': test_history,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def edit_profile(request: HttpRequest) -> HttpResponse:
    user = request.user
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save(update_fields=['first_name', 'last_name', 'email'])
        messages.success(request, 'Профиль сохранён.')
        return redirect('profile')
    return render(request, 'edit_profile.html')


@login_required
@require_POST
def profile_delete(request: HttpRequest) -> HttpResponse:
    user = request.user
    logout(request)
    user.delete()
    messages.info(request, 'Аккаунт удалён.')
    return redirect('home')


# --- Попытка целиком (quiz_db: attempt_*.html) ------------------------------------


@login_required
@require_POST
def quiz_start(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    if _attempts_used(user=request.user, quiz=quiz) >= quiz.max_attempts:
        messages.error(request, 'Достигнут лимит попыток для этого теста.')
        return redirect('quiz_detail', quiz_id=quiz.pk)

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


@login_required
@require_POST
def attempt_cancel(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt,
        pk=attempt_id,
        student=request.user,
        submitted_at__isnull=True,
    )
    quiz_id = attempt.quiz_id
    attempt.delete()
    messages.info(request, 'Попытка отменена.')
    return redirect('quiz_detail', quiz_id=quiz_id)
