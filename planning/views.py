from django.shortcuts import get_object_or_404
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

from event.models import Event, Subtask
from event.views.mixins import OrganizerMixin

from .serializers import DayProgressSerializer, TodaySubtaskSerializer
from .services import day_progress, group_subtasks


@extend_schema(
    summary="Day summary",
    description="""
Groups the organizer's subtasks for today: overdue (pending with a past
date), today's (pending and done, kept separate) and upcoming ones within
`dias_proximos` days. Also includes the day's progress (subtasks and hours
completed vs. total). Can be filtered by `event_id` and/or `status`.
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
        OpenApiParameter(
            name="event_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filters every list and the progress bar to a single event owned by "
                        "the organizer. 404 if it doesn't exist or belongs to another organizer.",
        ),
        OpenApiParameter(
            name="status",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="pending|done|postponed (or alias PENDING|EXECUTED|POSTPONED). Filters "
                        "the subtask lists; 'pospuestas' only shows up with status=postponed "
                        "and covers dates up to today + dias_proximos. "
                        "Doesn't affect the day's progress bar.",
        ),
    ],
    responses={
        200: OpenApiResponse(description="Day summary"),
        400: OpenApiResponse(description="Invalid dias_proximos, metrica or status"),
        404: OpenApiResponse(description="event_id doesn't exist or belongs to another organizer"),
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
                "filtros": {"event_id": None, "status": None},
            },
            response_only=True,
        )
    ],
)
class TodayView(OrganizerMixin, APIView):
    VALID_METRICS = ("gestiones", "horas")
    # Aliases accepted by the frontend besides the model's native values.
    STATUS_ALIASES = {"PENDING": "pending", "EXECUTED": "done", "POSTPONED": "postponed"}

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

    def _status(self, request):
        raw = request.query_params.get("status")
        if raw is None:
            return None
        value = self.STATUS_ALIASES.get(raw, raw)
        if value not in dict(Subtask.STATUS_CHOICES):
            raise ValidationError("El estado no es válido.")
        return value

    def _event_id(self, request, organizer):
        raw = request.query_params.get("event_id")
        if raw is None:
            return None
        try:
            event_id = int(raw)
        except (TypeError, ValueError):
            raise ValidationError("event_id debe ser un número entero.")
        # 404 both when it doesn't exist and when it belongs to another
        # organizer: we don't leak the existence of someone else's events.
        event = get_object_or_404(Event, eid=event_id, user=organizer)
        return event.eid

    def get(self, request, *args, **kwargs):
        dias_proximos = self._dias_proximos(request)
        metrica = self._metrica(request)
        organizer = self.get_organizer()
        event_id = self._event_id(request, organizer)
        status_filter = self._status(request)
        today = timezone.localdate()

        groups = group_subtasks(
            organizer, today, event_id=event_id, days_ahead=dias_proximos, status=status_filter
        )
        # The day's progress bar isn't filtered by status: it's the
        # pending/done split of today, not a filterable list.
        progress = day_progress(organizer, today, event_id=event_id)

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
            "filtros": {"event_id": event_id, "status": status_filter},
        }
        # "pospuestas" only travels when that status was explicitly requested.
        if status_filter == "postponed":
            data["pospuestas"] = TodaySubtaskSerializer(
                groups["postponed"], many=True, context=context
            ).data
        return Response(data)
