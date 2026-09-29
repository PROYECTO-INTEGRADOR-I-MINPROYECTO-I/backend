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

from .serializers import DayProgressSerializer, TodaySubtaskSerializer
from .services import day_progress, group_subtasks


@extend_schema(
    summary="Day summary",
    description="""
Groups the organizer's subtasks for today: overdue (pending with a past
date), today's (pending and done, kept separate) and upcoming ones within
`dias_proximos` days. Also includes the day's progress (subtasks and hours
completed vs. total).
    """,
    tags=["Today"],
    parameters=[
        OpenApiParameter(
            name="dias_proximos",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Look-ahead window for 'proximas' (1 to 60, default 7).",
        ),
        OpenApiParameter(
            name="metrica",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="'gestiones' or 'horas' (default 'gestiones'). Only changes the "
                        "response's 'metrica' field: both metrics always travel in "
                        "'progreso_dia'.",
        ),
    ],
    responses={
        200: OpenApiResponse(description="Day summary"),
        400: OpenApiResponse(description="Invalid dias_proximos or metrica"),
    },
    examples=[
        OpenApiExample(
            "Example response",
            value={
                "fecha": "2026-09-27",
                "metrica": "gestiones",
                "vencidas": [],
                "para_hoy": {"pendientes": [], "completadas": []},
                "proximas": [],
                "progreso_dia": {
                    "completadas": 1,
                    "total": 3,
                    "horas_completadas": "2.00",
                    "horas_totales": "6.00",
                },
            },
            response_only=True,
        )
    ],
)
class TodayView(OrganizerMixin, APIView):
    VALID_METRICS = ("gestiones", "horas")

    def _dias_proximos(self, request):
        raw = request.query_params.get("dias_proximos", "7")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValidationError("dias_proximos debe ser un entero entre 1 y 60.")
        if not 1 <= value <= 60:
            raise ValidationError("dias_proximos debe ser un entero entre 1 y 60.")
        return value

    def _metrica(self, request):
        value = request.query_params.get("metrica", "gestiones")
        if value not in self.VALID_METRICS:
            raise ValidationError("La métrica debe ser 'gestiones' u 'horas'.")
        return value

    def get(self, request, *args, **kwargs):
        dias_proximos = self._dias_proximos(request)
        metrica = self._metrica(request)
        today = timezone.localdate()
        organizer = self.get_organizer()

        groups = group_subtasks(organizer, today, days_ahead=dias_proximos)
        progress = day_progress(organizer, today)

        context = {"organizer": organizer}
        data = {
            "fecha": str(today),
            "metrica": metrica,
            "vencidas": TodaySubtaskSerializer(groups["overdue"], many=True, context=context).data,
            "para_hoy": {
                "pendientes": TodaySubtaskSerializer(
                    groups["today"]["pending"], many=True, context=context
                ).data,
                "completadas": TodaySubtaskSerializer(
                    groups["today"]["done"], many=True, context=context
                ).data,
            },
            "proximas": TodaySubtaskSerializer(groups["upcoming"], many=True, context=context).data,
            "progreso_dia": DayProgressSerializer(progress).data,
        }
        return Response(data)
