from django.urls import path

from .views import health, test, EventListCreateView


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
    path('eventos/', EventListCreateView.as_view(), name='event-create')
]
