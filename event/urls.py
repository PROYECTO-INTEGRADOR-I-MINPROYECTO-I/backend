from django.urls import path

from .views import (
    health,
    test,
    EventListCreateView,
    EventDetailView,
    EventSubtaskListCreateView,
    SubtaskDetailView,
    CurrentUserView,
    UserRegisterView,
    EventTypeListCreateView,
    CategoryListCreateView,
)


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create'),
    path('eventos/<int:eid>/', EventDetailView.as_view(), name='event-detail'),
    path('eventos/<int:eid>/subtareas/', EventSubtaskListCreateView.as_view(), name='event-subtasks'),
    path('subtareas/<int:subtask_id>/', SubtaskDetailView.as_view(), name='subtask-detail'),
    path('yo/', CurrentUserView.as_view(), name='current-user'),
    path('register/', UserRegisterView.as_view(), name='user-register'),
    path('tipos-evento/', EventTypeListCreateView.as_view(), name='event-type-create'),
    path('categorias/', CategoryListCreateView.as_view(), name='category-create'),
    ]
