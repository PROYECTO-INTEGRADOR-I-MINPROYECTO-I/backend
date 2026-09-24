from django.urls import path

from .views import health, test, EventListCreateView, EventSubtaskListCreateView, UserListCreateView


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create'),
    path('eventos/<int:eid>/subtareas/', EventSubtaskListCreateView.as_view(), name='event-subtasks'),
    path('usuarios/', UserListCreateView.as_view(), name='user-create'),
    ]
