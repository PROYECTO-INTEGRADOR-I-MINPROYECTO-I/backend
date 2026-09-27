from django.shortcuts import get_object_or_404
from django.utils import timezone

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from planning.services import LOAD_STATUSES, evaluate_overload

from ..models import Event, Subtask
from ..serializers import SubtaskSerializer
from .mixins import OrganizerMixin


def _serialize_conflict(conflict):
    # planned_hours/limit/date travel as strings: DRF's JSONEncoder would
    # otherwise turn the Decimal into a float, and here we want the same
    # format estimated_hours already uses elsewhere in the API.
    return {
        "has_conflict": conflict["has_conflict"],
        "planned_hours": str(conflict["planned_hours"]),
        "limit": str(conflict["limit"]),
        "date": str(conflict["date"]),
        "message": conflict["message"],
    }


@extend_schema_view(
    get=extend_schema(
        summary="List subtasks for a specific event",
        description="Returns the subtasks that belong to the event in the URL.",
        parameters=[
            OpenApiParameter(
                name="eid",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID of the parent event",
            )
        ],
        tags=["Subtasks"],
    ),
    post=extend_schema(
        summary="Create a new subtask",
        description="""
Creates a new subtask associated with a specific event.

* **Note:** the response includes a `warnings` list (e.g. when the
subtask's target date falls after the event's due date).

* **Overload:** if this subtask pushes the day past the organizer's daily
limit, the message is added to `warnings` plus a `conflict` object
(`has_conflict`, `planned_hours`, `limit`, `date`, `message`). It doesn't
block saving.
        """,
        parameters=[
            OpenApiParameter(
                name="eid",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID of the parent event",
            )
        ],
        tags=["Subtasks"],
        request=SubtaskSerializer,
        responses={
            201: SubtaskSerializer,
            400: OpenApiResponse(description="Validation error (e.g. empty title or invalid hours)"),
            404: OpenApiResponse(description="Parent Event not found"),
        },
        examples=[
            OpenApiExample(
                "Valid Subtask Payload",
                summary="Example of a valid subtask request",
                value={
                    "title": "Cotizar catering",
                    "description": "Pedir cotización a tres proveedores",
                    "category": "Catering",
                    "estimated_hours": 3,
                    "scheduled_date": "2026-10-15",
                    "status": "pending",
                },
                request_only=True,
            )
        ],
    ),
)
class EventSubtaskListCreateView(OrganizerMixin, ListCreateAPIView):
    serializer_class = SubtaskSerializer

    def get_event(self):
        if not hasattr(self, "_event"):
            self._event = get_object_or_404(
                Event, pk=self.kwargs['eid'], user=self.get_organizer()
            )
        return self._event

    def get_queryset(self):
        return Subtask.objects.filter(eid=self.get_event()).select_related("category")

    def perform_create(self, serializer):
        # Evaluate the overload conflict BEFORE saving: this way daily_load
        # only sees the already-existing subtasks and we add new_hours
        # separately, no need to exclude the subtask (it doesn't exist yet).
        date = serializer.validated_data["scheduled_date"]
        hours = serializer.validated_data["estimated_hours"]
        self._conflict = evaluate_overload(self.get_organizer(), date, hours)
        # Created already done: stamp it like a PATCH to "done" would.
        done = serializer.validated_data.get("status") == "done"
        serializer.save(eid=self.get_event(), executed_at=timezone.now() if done else None)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        warnings = []
        event = self.get_event()
        scheduled_date = response.data.get("scheduled_date")
        if scheduled_date and str(scheduled_date) > str(event.due_date.date()):
            warnings.append("La fecha objetivo es posterior a la fecha del evento")

        conflict = getattr(self, "_conflict", None)
        if conflict and conflict["has_conflict"]:
            warnings.append(conflict["message"])
            response.data["conflict"] = _serialize_conflict(conflict)

        if warnings:
            response.data["warnings"] = warnings
        return response


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a subtask",
        description="Returns a single subtask that belongs to an event owned by the current organizer.",
        tags=["Subtasks"],
    ),
    patch=extend_schema(
        summary="Partially update a subtask",
        description="""
        Updates one or more fields of a subtask. `eid` is read-only: a
        subtask cannot be moved to another event.

        Setting `status` to `"done"` stamps `executed_at` with the current
        time; moving it away from `"done"` clears `executed_at`.

        If the new date/hours overload the day, the response carries
        `warnings` and a `conflict` object (same shape as on create).
        """,
        tags=["Subtasks"],
        responses={
            200: SubtaskSerializer,
            400: OpenApiResponse(description="Validation error (e.g. empty title or invalid hours)"),
            404: OpenApiResponse(description="Subtask not found for the current organizer"),
        },
    ),
    delete=extend_schema(
        summary="Delete a subtask",
        description="Deletes a subtask owned (through its event) by the current organizer.",
        tags=["Subtasks"],
        responses={204: None, 404: OpenApiResponse(description="Subtask not found for the current organizer")},
    ),
)
class SubtaskDetailView(OrganizerMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = SubtaskSerializer
    lookup_field = "subtask_id"
    lookup_url_kwarg = "subtask_id"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Subtask.objects.for_organizer(self.get_organizer())

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        # Fields that can shift the day's load: date, effort or status (only
        # matters if it ends up pending/done, see LOAD_STATUSES).
        relevant_fields = {"scheduled_date", "estimated_hours", "status"}
        load_changed = relevant_fields & set(serializer.validated_data.keys())

        instance = serializer.save()
        # Only stamp on a real transition, so retrying "done" keeps the original time.
        if instance.status != previous_status and "done" in (instance.status, previous_status):
            instance.executed_at = timezone.now() if instance.status == "done" else None
            instance.save(update_fields=["executed_at"])

        self._conflict = None
        if load_changed and instance.status in LOAD_STATUSES:
            self._conflict = evaluate_overload(
                self.get_organizer(),
                instance.scheduled_date,
                instance.estimated_hours,
                exclude_subtask_id=instance.pk,
            )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)

        conflict = getattr(self, "_conflict", None)
        if conflict and conflict["has_conflict"]:
            response.data["warnings"] = [conflict["message"]]
            response.data["conflict"] = _serialize_conflict(conflict)

        return response
