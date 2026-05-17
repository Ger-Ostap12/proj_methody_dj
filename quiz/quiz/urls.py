"""
URL configuration for quiz project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('quiz.auth_urls')),
    path('auth/register/', include('users.urls')),
    path('', include('quiz_db.urls')),
]
