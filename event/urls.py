from django.urls import path

from .views import health, test, EventListCreateView, EventSubtaskListCreateView, CurrentUserView, UserRegisterView


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create'),
    path('eventos/<int:eid>/subtareas/', EventSubtaskListCreateView.as_view(), name='event-subtasks'),
    path('yo/', CurrentUserView.as_view(), name='current-user'),
    path('register/', UserRegisterView.as_view(), name='user-register'),
    ]
