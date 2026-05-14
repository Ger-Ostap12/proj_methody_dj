from django.contrib import admin

from .models import (
    AnswerOption,
    Question,
    Quiz,
    QuizAttempt,
    StudentAnswer,
    UserProfile,
)


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 1


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'author',
        'is_published',
        'time_limit_minutes',
        'max_attempts',
        'created_at',
    )
    list_filter = ('is_published',)
    search_fields = ('title', 'description')
    autocomplete_fields = ('author',)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'short_text', 'question_type', 'order')
    list_filter = ('question_type',)
    search_fields = ('text', 'quiz__title')
    inlines = [AnswerOptionInline]

    @admin.display(description='Текст вопроса')
    def short_text(self, obj):
        t = obj.text
        return t if len(t) <= 60 else f'{t[:60]}…'


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('question', 'short_text', 'is_correct', 'order')
    list_filter = ('is_correct',)
    search_fields = ('text', 'question__text')

    @admin.display(description='Текст варианта')
    def short_text(self, obj):
        t = obj.text
        return t if len(t) <= 40 else f'{t[:40]}…'


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'quiz',
        'score',
        'max_score',
        'started_at',
        'submitted_at',
    )
    list_filter = ('quiz',)
    search_fields = ('student__username', 'quiz__title')
    autocomplete_fields = ('student', 'quiz')
    date_hierarchy = 'started_at'


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question')
    autocomplete_fields = ('attempt', 'question')
    filter_horizontal = ('selected_options',)
