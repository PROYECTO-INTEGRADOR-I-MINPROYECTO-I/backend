from decimal import Decimal

from django.utils import timezone

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from event.views.mixins import OrganizerMixin

from .serializers import TodaySubtaskSerializer
from .services import day_progress, group_subtasks


def _serialize_day_progress(progress):
    # Same format estimated_hours already uses (2-decimal DecimalField, as a
    # string): otherwise DRF's JSONEncoder would turn the Decimal into a float.
    return {
        "completed": progress["completed"],
        "total": progress["total"],
        "completed_hours": str(progress["completed_hours"].quantize(Decimal("0.01"))),
        "total_hours": str(progress["total_hours"].quantize(Decimal("0.01"))),
    }


@extend_schema(
    summary="Day summary",
    description="""
Groups the organizer's subtasks for today: overdue (pending with a past
date), today's (pending and done, kept separate) and upcoming ones within
`days_ahead` days. Also includes the day's progress (subtasks and hours
completed vs. total).
    """,
    tags=["Today"],
    parameters=[
        OpenApiParameter(
            name="days_ahead",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Look-ahead window for 'upcoming' (1 to 60, default 7).",
        ),
        OpenApiParameter(
            name="metric",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="'subtasks' or 'hours' (default 'subtasks'). Only changes the response's "
                        "'metric' field: both metrics always travel in day_progress.",
        ),
    ],
    responses={
        200: OpenApiResponse(description="Day summary"),
        400: OpenApiResponse(description="Invalid days_ahead or metric"),
    },
    examples=[
        OpenApiExample(
            "Example response",
            value={
                "date": "2026-09-27",
                "metric": "subtasks",
                "overdue": [],
                "today": {"pending": [], "done": []},
                "upcoming": [],
                "day_progress": {
                    "completed": 1,
                    "total": 3,
                    "completed_hours": "2.00",
                    "total_hours": "6.00",
                },
            },
            response_only=True,
        )
    ],
)
class TodayView(OrganizerMixin, APIView):
    VALID_METRICS = ("subtasks", "hours")

    def _days_ahead(self, request):
        raw = request.query_params.get("days_ahead", "7")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValidationError("El rango de días debe ser un entero entre 1 y 60.")
        if not 1 <= value <= 60:
            raise ValidationError("El rango de días debe ser un entero entre 1 y 60.")
        return value

    def _metric(self, request):
        value = request.query_params.get("metric", "subtasks")
        if value not in self.VALID_METRICS:
            raise ValidationError("metric debe ser 'subtasks' u 'hours'.")
        return value

    def get(self, request, *args, **kwargs):
        days_ahead = self._days_ahead(request)
        metric = self._metric(request)
        today = timezone.localdate()
        organizer = self.get_organizer()

        groups = group_subtasks(organizer, today, days_ahead=days_ahead)
        progress = day_progress(organizer, today)

        context = {"organizer": organizer}
        data = {
            "date": str(today),
            "metric": metric,
            "overdue": TodaySubtaskSerializer(groups["overdue"], many=True, context=context).data,
            "today": {
                "pending": TodaySubtaskSerializer(
                    groups["today"]["pending"], many=True, context=context
                ).data,
                "done": TodaySubtaskSerializer(
                    groups["today"]["done"], many=True, context=context
                ).data,
            },
            "upcoming": TodaySubtaskSerializer(groups["upcoming"], many=True, context=context).data,
            "day_progress": _serialize_day_progress(progress),
        }
        return Response(data)
