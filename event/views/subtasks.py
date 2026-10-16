from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response

from planning.services import evaluate_conflict

from ..models import Event, Subtask
from ..serializers import SubtaskCreateRequestSerializer, SubtaskSerializer
from .conflicts import lock_organizer, overload_response, parse_confirm
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
* **Overload:** if the day would exceed the organizer's daily hour limit
the request answers `409` (`DAILY_OVERLOAD`, with alternatives) and nothing
is saved. Send `"confirm": true` to create it anyway.
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
        request=SubtaskCreateRequestSerializer,
        responses={
            201: SubtaskSerializer,
            400: OpenApiResponse(description="Validation error (e.g. empty title or invalid hours)"),
            404: OpenApiResponse(description="Parent Event not found"),
            409: OpenApiResponse(description="DAILY_OVERLOAD: the day would exceed the daily limit (retry with confirm=true)"),
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
                    "confirm": False,
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
        # Created already done: stamp it like a PATCH to "done" would.
        done = serializer.validated_data.get("status") == "done"
        serializer.save(eid=self.get_event(), executed_at=timezone.now() if done else None)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        confirm = parse_confirm(request.data)
        with transaction.atomic():
            if data.get("status", "pending") != "postponed" and not confirm:
                organizer = self.get_organizer()
                lock_organizer(organizer)
                evaluation = evaluate_conflict(
                    organizer, data["scheduled_date"], data["estimated_hours"]
                )
                if evaluation["has_conflict"]:
                    return overload_response(evaluation)
            self.perform_create(serializer)
        response = Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data),
        )

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
