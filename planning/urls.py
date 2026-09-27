from django.urls import path

from .views import TodayView

urlpatterns = [
    path('today/', TodayView.as_view(), name='today'),
]
