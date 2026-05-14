"""Маршруты приложения ``quiz_db``."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('quiz/<int:pk>/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:pk>/start/', views.quiz_start, name='quiz_start'),
    path('attempt/<int:attempt_id>/', views.attempt_take, name='attempt_take'),
    path('attempt/<int:attempt_id>/submit/', views.attempt_submit, name='attempt_submit'),
    path('attempt/<int:attempt_id>/result/', views.attempt_result, name='attempt_result'),
]
