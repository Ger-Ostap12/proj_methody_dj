import logging
from django.conf import settings
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.http import HttpResponseRedirect
from django.shortcuts import render, resolve_url


logger = logging.getLogger('predictions')


def home(request):
    logger.info("Открыта главная страница")
    return render(request, 'index.html')


class LogoutView(DjangoLogoutView):
    """
    Стандартный LogoutView в Django 5+ принимает только POST; GET даёт 405 с пустым телом.
    GET показывает страницу с кнопкой «Выйти» (POST с CSRF); POST — выход и редирект.
    """

    http_method_names = ['get', 'head', 'post', 'options']

    def get(self, request, *args, **kwargs):
        try:
            if not request.user.is_authenticated:
                logger.warning("Выход: GET без авторизации — редирект на вход")
                return HttpResponseRedirect(resolve_url(settings.LOGIN_URL))
            logger.info("Выход: GET — показ страницы подтверждения")
            return render(request, 'registration/logout_confirm.html')
        except Exception:
            logger.exception("Выход: ошибка при обработке GET")
            raise

# ===== ВРЕМЕННЫЕ ЗАГЛУШКИ ДЛЯ ПРОФИЛЯ И ТЕСТОВ =====
# (пока бэкенд не готов, эти функции позволяют увидеть страницы)

def profile(request):
    """Временная заглушка для страницы профиля"""
    logger.info("Открыта страница профиля")
    return render(request, 'profile.html', {
        'total_tests_passed': 0,
        'average_score': 0,
        'best_score': 0,
        'test_history': []
    })


def edit_profile(request):
    """Временная заглушка для редактирования профиля"""
    logger.info("Открыта страница редактирования профиля")
    return render(request, 'edit_profile.html')


def quiz_list(request):
    """Временная заглушка для списка тестов"""
    logger.info("Открыт список тестов")
    return render(request, 'quiz_list.html', {
        'tests': [],
        'search_query': '',
        'difficulty': ''
    })


def quiz_detail(request, quiz_id):
    """Временная заглушка для страницы теста"""
    logger.info("Открыта страница теста")
    return render(request, 'quiz_detail.html', {
        'quiz_title': f'Тест #{quiz_id}',
        'quiz_id': quiz_id,
        'current_question': 1,
        'total_questions': 10,
        'question_text': 'Это временный вопрос. Скоро здесь будут настоящие тесты!',
        'options': [
            {'id': 1, 'text': 'Вариант ответа 1'},
            {'id': 2, 'text': 'Вариант ответа 2'},
            {'id': 3, 'text': 'Вариант ответа 3'},
            {'id': 4, 'text': 'Вариант ответа 4'},
        ]
    })


def submit_answer(request, quiz_id):
    """Временная заглушка для отправки ответа"""
    if request.method != 'POST':
        logger.warning("Отправка ответа: неожиданный метод запроса (ожидался POST)")
    logger.info("Отправка ответа на тест")
    return render(request, 'result.html', {
        'score_percent': 75,
        'correct_answers': 75,
        'total_questions': 100,
        'quiz_id': quiz_id,
        'mistakes': []
    })


def result(request, result_id):
    """Временная заглушка для страницы результатов"""
    logger.info("Открыта страница результатов")
    return render(request, 'result.html', {
        'score_percent': 80,
        'correct_answers': 8,
        'total_questions': 10,
        'quiz_id': 1,
        'mistakes': []
    })


def toggle_favorite(request, quiz_id):
    """Временная заглушка для избранного"""
    if request.method not in ('POST', 'GET'):
        logger.warning("Избранное: неожиданный метод запроса")
    logger.info("Переключение избранного для теста")
    # Просто возвращаем обратно на страницу списка тестов
    from django.shortcuts import redirect
    return redirect('quiz_list')
