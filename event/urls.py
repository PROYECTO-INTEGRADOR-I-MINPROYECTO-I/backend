from django.urls import path

from .views import (
    health,
    test,
    EventListCreateView,
    EventDetailView,
    EventSubtaskListCreateView,
    SubtaskDetailView,
    EventTypeListCreateView,
    CategoryListCreateView,
)
from .auth_views import LoginView, LogoutView, MeView, RegisterView


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create'),
    path('eventos/<int:eid>/', EventDetailView.as_view(), name='event-detail'),
    path('eventos/<int:eid>/subtareas/', EventSubtaskListCreateView.as_view(), name='event-subtasks'),
    path('subtareas/<int:subtask_id>/', SubtaskDetailView.as_view(), name='subtask-detail'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('tipos-evento/', EventTypeListCreateView.as_view(), name='event-type-create'),
    path('categorias/', CategoryListCreateView.as_view(), name='category-create'),
    ]
