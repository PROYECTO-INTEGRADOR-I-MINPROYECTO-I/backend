from django.urls import path

from .views import health, test, EventListCreateView, EventSubtaskListCreateView


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create'),
    path('eventos/<int:event_id>/subtareas/', EventSubtaskListCreateView.as_view(), name='event-subtasks')
    ]
