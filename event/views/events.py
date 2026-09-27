from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from ..models import Event
from ..serializers import EventSerializer
from .mixins import OrganizerMixin


@extend_schema_view(
    get=extend_schema(
        summary="List all events",
        description="Returns list of all created events",
        tags=["Eventos"],
    ),
    post=extend_schema(
        summary="Create an event",
        description="Creates a new event attached to the current organizer.",
        tags=["Eventos"],
        examples=[
                OpenApiExample(
                    "Valid Subtask Payload",
                    summary="Example of a valid event request",
                    value={
                        "name": "Boda Natalia & Julio",
                        "description": "Planeación de boda completa.",
                        "due_date": "2026-09-25",
                        "event_type": 1,
                        "place": "Salón de Evento Cañasgoardas",
                        "client_contact": "123-456-8790"
                    },
                    request_only=True,
                )
            ],
    ),
)
class EventListCreateView(OrganizerMixin, ListCreateAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.filter(user=self.get_organizer()).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.get_organizer())


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve an event",
        description="Returns a single event owned by the current organizer.",
        tags=["Eventos"],
    ),
    patch=extend_schema(
        summary="Partially update an event",
        description="Updates one or more fields of an event owned by the current organizer.",
        tags=["Eventos"],
        responses={
            200: EventSerializer,
            400: OpenApiResponse(description="Validation error (e.g. empty name or past due date)"),
            404: OpenApiResponse(description="Event not found for the current organizer"),
        },
    ),
    delete=extend_schema(
        summary="Delete an event",
        description="Deletes an event owned by the current organizer. Its subtasks are deleted in cascade.",
        tags=["Eventos"],
        responses={204: None, 404: OpenApiResponse(description="Event not found for the current organizer")},
    ),
)
class EventDetailView(OrganizerMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = EventSerializer
    lookup_field = "eid"
    lookup_url_kwarg = "eid"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Event.objects.filter(user=self.get_organizer())
