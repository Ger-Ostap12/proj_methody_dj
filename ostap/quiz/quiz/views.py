from django.conf import settings
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.http import HttpResponseRedirect
from django.shortcuts import render, resolve_url


class LogoutView(DjangoLogoutView):
    """
    Стандартный LogoutView в Django 5+ принимает только POST; GET даёт 405 с пустым телом.
    GET показывает страницу с кнопкой «Выйти» (POST с CSRF); POST — выход и редирект.
    """

    http_method_names = ['get', 'head', 'post', 'options']

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(resolve_url(settings.LOGIN_URL))
        return render(request, 'registration/logout_confirm.html')
