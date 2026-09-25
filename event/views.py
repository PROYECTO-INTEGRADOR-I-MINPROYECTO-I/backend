from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)

from .models import Events, Subtasks, Users, EventType, Category
from .exceptions import Conflict
from .organizer import get_current_organizer
from .serializers import (
    EventSerializer,
    SubtaskSerializer,
    UserSerializer,
    EventTypeSerializer,
    CategorySerializer,
)


def test(request):
    return JsonResponse({
        "message": "Server is working!"
    })


def health(request):
    """Health check del servicio.

    Render consulta este endpoint para decidir si el deploy quedó sano y para
    vigilar el servicio después. No basta con responder 200: si la aplicación
    está viva pero no alcanza la base de datos, no puede atender nada útil,
    así que comprobamos también la conexión.

    Devuelve 200 si todo responde y 503 si la base de datos no contesta, que es
    lo que Render interpreta como servicio caído.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {
                "status": "unhealthy",
                "environment": settings.ENVIRONMENT,
                "database": "error",
                # El detalle solo en dev: en qa/prod expondría datos de la
                # infraestructura (host, usuario) en un endpoint público.
                "detail": str(exc) if settings.DEBUG else None,
            },
            status=503,
        )

    return JsonResponse({
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "database": "ok",
    })


class OrganizerMixin:
    """Resuelve el organizador "actual" (stub PIM1-91) y lo pasa al serializer."""

    def get_organizer(self):
        # Cached per request: several hooks (context, queryset, save) need it.
        if not hasattr(self, "_organizer"):
            self._organizer = get_current_organizer(self.request)
        return self._organizer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organizer"] = self.get_organizer()
        return context


# Generic view for Event view
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
    ),
)
class EventListCreateView(OrganizerMixin, ListCreateAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Events.objects.filter(user=self.get_organizer()).order_by('-created_at')

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
        return Events.objects.filter(user=self.get_organizer())


@extend_schema_view(
    get=extend_schema(
        summary="List all users",
        description="Returns list of all registered users.",
        tags=["Usuarios"],
    ),
    post=extend_schema(
        summary="Register a new user.",
        description="Creates a new user registry.",
        tags=["Usuarios"],
    ),
)
class UserListCreateView(ListCreateAPIView):
    queryset = Users.objects.all()
    serializer_class = UserSerializer


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
                Events, pk=self.kwargs['eid'], user=self.get_organizer()
            )
        return self._event

    def get_queryset(self):
        return Subtasks.objects.filter(eid=self.get_event())

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
        return Subtasks.objects.filter(eid__user=self.get_organizer())

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        instance = serializer.save()
        # Only on a real transition, so a retried {"status": "done"} keeps the
        # original completion time.
        if instance.status != previous_status and "done" in (instance.status, previous_status):
            instance.executed_at = timezone.now() if instance.status == "done" else None
            instance.save(update_fields=["executed_at"])


@extend_schema_view(
    get=extend_schema(
        summary="List event types",
        description="Returns the predefined event types plus the organizer's own.",
        tags=["Tipos de evento"],
    ),
    post=extend_schema(
        summary="Create an event type",
        description="Creates a new event type for the current organizer.",
        tags=["Tipos de evento"],
    ),
)
class EventTypeListCreateView(OrganizerMixin, ListCreateAPIView):
    serializer_class = EventTypeSerializer

    def get_queryset(self):
        organizer = self.get_organizer()
        return EventType.objects.filter(
            Q(user__isnull=True) | Q(user=organizer)
        ).order_by('name')

    def perform_create(self, serializer):
        # validate_name already returns 409; this covers two concurrent POSTs
        # that both pass validation and collide on the unique constraint.
        try:
            with transaction.atomic():
                serializer.save(user=self.get_organizer())
        except IntegrityError:
            raise Conflict("Ya tienes un tipo de evento con ese nombre")


@extend_schema_view(
    get=extend_schema(
        summary="List categories",
        description="Returns the predefined categories plus the organizer's own.",
        tags=["Categorías"],
    ),
    post=extend_schema(
        summary="Create a category",
        description="Creates a new category for the current organizer.",
        tags=["Categorías"],
    ),
)
class CategoryListCreateView(OrganizerMixin, ListCreateAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        organizer = self.get_organizer()
        return Category.objects.filter(
            Q(user__isnull=True) | Q(user=organizer)
        ).order_by('name')

    def perform_create(self, serializer):
        # validate_name already returns 409; this covers two concurrent POSTs
        # that both pass validation and collide on the unique constraint.
        try:
            with transaction.atomic():
                serializer.save(user=self.get_organizer())
        except IntegrityError:
            raise Conflict("Ya tienes una categoría con ese nombre")
