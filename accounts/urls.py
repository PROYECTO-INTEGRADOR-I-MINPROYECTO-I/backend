from django.urls import path

from .views import CurrentUserView, UserRegisterView

urlpatterns = [
    path('yo/', CurrentUserView.as_view(), name='current-user'),
    path('register/', UserRegisterView.as_view(), name='user-register'),
]
