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

from ..models import Event, Subtask
from ..serializers import SubtaskSerializer
from .mixins import OrganizerMixin


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
        return Subtask.objects.filter(eid=self.get_event())

    def perform_create(self, serializer):
        serializer.save(eid=self.get_event())

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        warnings = []
        event = self.get_event()
        scheduled_date = response.data.get("scheduled_date")
        if scheduled_date and str(scheduled_date) > str(event.due_date.date()):
            warnings.append("La fecha objetivo es posterior a la fecha del evento")

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
        instance = serializer.save()
        # Only stamp on a real transition, so retrying "done" keeps the original time.
        if instance.status != previous_status and "done" in (instance.status, previous_status):
            instance.executed_at = timezone.now() if instance.status == "done" else None
            instance.save(update_fields=["executed_at"])
