import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm


logger = logging.getLogger('predictions')

def register(request):
    if request.method == 'POST':
        logger.info("Регистрация: получен POST-запрос")
        form = CustomUserCreationForm(request.POST) #созд объект формы
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info("Регистрация: пользователь успешно создан и вошёл в систему")
            return redirect('/')
        logger.warning("Регистрация: форма невалидна")
    else:
        if request.method != 'GET':
            logger.warning("Регистрация: неожиданный метод запроса (ожидался GET или POST)")
        logger.info("Регистрация: открыт экран регистрации (GET)")
        form = CustomUserCreationForm()

    return render(request, 'registration/register.html', {'form': form})