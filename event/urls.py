from django.urls import path

from .views import health, test


urlpatterns = [
    path("health/", health, name="health"),
    path("test/", test),
]
