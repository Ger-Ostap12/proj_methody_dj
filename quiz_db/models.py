from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class UserRole(models.TextChoices):
    TEACHER = 'teacher', 'Преподаватель'
    STUDENT = 'student', 'Студент'


class UserProfile(models.Model):
    """Роль пользователя для разграничения прав преподаватель / студент."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_profile',
        verbose_name='Пользователь',
    )
    role = models.CharField(
        max_length=16,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        verbose_name='Роль',
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self) -> str:
        return f'{self.user.get_username()} ({self.get_role_display()})'


class QuestionType(models.TextChoices):
    SINGLE = 'single', 'Одиночный выбор'
    MULTIPLE = 'multiple', 'Множественный выбор'


class Quiz(models.Model):
    """Тест: название, описание, время на прохождение, публикация, автор, лимит попыток."""

    title = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    time_limit_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Время на прохождение (мин.)',
    )
    is_published = models.BooleanField(default=False, verbose_name='Опубликован')
    max_attempts = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Максимум попыток',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='authored_quizzes',
        verbose_name='Автор (преподаватель)',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_published', '-created_at']),
        ]

    def __str__(self) -> str:
        return self.title


class Question(models.Model):
    """Вопрос теста: текст, тип выбора, порядок."""

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Тест',
    )
    text = models.TextField(verbose_name='Текст вопроса')
    question_type = models.CharField(
        max_length=16,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE,
        verbose_name='Тип вопроса',
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['quiz', 'order', 'pk']

    def __str__(self) -> str:
        return f'{self.quiz.title}: {self.text[:50]}'


class AnswerOption(models.Model):
    """Вариант ответа: текст, признак правильности, порядок отображения."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answer_options',
        verbose_name='Вопрос',
    )
    text = models.CharField(max_length=500, verbose_name='Текст варианта')
    is_correct = models.BooleanField(default=False, verbose_name='Правильный')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['question', 'order', 'pk']

    def __str__(self) -> str:
        mark = '✓' if self.is_correct else '✗'
        return f'{mark} {self.text[:40]}'


class QuizAttempt(models.Model):
    """
    Результат одной попытки: студент, тест, время начала/отправки, баллы.
    Для проверки таймера и лимита попыток используются started_at / submitted_at.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        verbose_name='Студент',
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Тест',
    )
    started_at = models.DateTimeField(verbose_name='Начало попытки')
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Отправлено',
    )
    score = models.PositiveIntegerField(default=0, verbose_name='Набрано баллов')
    max_score = models.PositiveIntegerField(default=0, verbose_name='Максимум баллов')

    class Meta:
        verbose_name = 'Попытка / результат'
        verbose_name_plural = 'Попытки / результаты'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'quiz', '-started_at']),
        ]

    def __str__(self) -> str:
        return f'{self.student.get_username()} — {self.quiz.title} ({self.score}/{self.max_score})'

    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None


class StudentAnswer(models.Model):
    """Ответ студента на вопрос в рамках попытки (выбранные варианты)."""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='student_answers',
        verbose_name='Попытка',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='student_answers',
        verbose_name='Вопрос',
    )
    selected_options = models.ManyToManyField(
        AnswerOption,
        blank=True,
        related_name='selected_in_answers',
        verbose_name='Выбранные варианты',
    )

    class Meta:
        verbose_name = 'Ответ студента'
        verbose_name_plural = 'Ответы студентов'
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'question'],
                name='studentanswer_unique_attempt_question',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.attempt} → вопрос {self.question_id}'
