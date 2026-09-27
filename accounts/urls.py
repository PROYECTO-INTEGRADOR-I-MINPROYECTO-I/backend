from django.urls import path

from .views import LoginView, LogoutView, MeView, RegisterView, UserSettingsView

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('user/settings/', UserSettingsView.as_view(), name='user-settings'),
]
