from django.urls import path

from .views import TodayView

urlpatterns = [
    path('hoy/', TodayView.as_view(), name='today'),
]
