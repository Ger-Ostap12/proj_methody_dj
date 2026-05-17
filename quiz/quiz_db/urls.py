"""Маршруты quiz_db — согласованы с post.py и шаблонами anasteysha."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('tests/', views.quiz_list, name='quiz_list'),
    path('tests/<int:test_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/delete/', views.profile_delete, name='profile_delete'),
    path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:quiz_id>/answer/', views.submit_answer, name='submit_answer'),
    path('quiz/<int:quiz_id>/result/', views.quiz_result, name='quiz_result'),
    path('quiz/<int:quiz_id>/start/', views.quiz_start, name='quiz_start'),
    path('attempt/<int:attempt_id>/', views.attempt_take, name='attempt_take'),
    path('attempt/<int:attempt_id>/submit/', views.attempt_submit, name='attempt_submit'),
    path('attempt/<int:attempt_id>/result/', views.attempt_result, name='attempt_result'),
    path('attempt/<int:attempt_id>/cancel/', views.attempt_cancel, name='attempt_cancel'),
]
