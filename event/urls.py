from django.urls import path

from .views import (
    CategoryListCreateView,
    EventDetailView,
    EventListCreateView,
    EventSubtaskListCreateView,
    EventTypeListCreateView,
    SubtaskDetailView,
    health,
    test,
)

urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create'),
    path('eventos/<int:eid>/', EventDetailView.as_view(), name='event-detail'),
    path('eventos/<int:eid>/subtareas/', EventSubtaskListCreateView.as_view(), name='event-subtasks'),
    path('subtareas/<int:subtask_id>/', SubtaskDetailView.as_view(), name='subtask-detail'),
    path('tipos-evento/', EventTypeListCreateView.as_view(), name='event-type-create'),
    path('categorias/', CategoryListCreateView.as_view(), name='category-create'),
    ]
