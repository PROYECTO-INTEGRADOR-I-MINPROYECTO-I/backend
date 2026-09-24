from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework.generics import ListCreateAPIView
from .models import Events, Subtasks, Users
from .serializers import EventSerializer, SubtaskSerializer, UserSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import ListCreateAPIView
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from rest_framework import status
from drf_spectacular.utils import extend_schema, extend_schema_view

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


# Generic view for Event view
@extend_schema_view(
    get=extend_schema(
        summary="List all events",
        description="Returns list of all created events",
        tags = ["Eventos"]
    ),
    post=extend_schema(
        summary="Create an event",
        description="Creates a new event attached to the user.",
        tags = ["Eventos"]
    )
)
class EventListCreateView(ListCreateAPIView):
    queryset = Events.objects.all()
    serializer_class = EventSerializer

@extend_schema_view(
    get=extend_schema(
        summary="List all users",
        description="Returns list of all registered users.",
        tags = ["Usuarios"]
    ),
    post=extend_schema(
        summary="Register a new user.",
        description="Creates a new user registry.",
        tags = ["Usuarios"]
    ),
)
class UserListCreateView(ListCreateAPIView):
    queryset = Users.objects.all()
    serializer_class = UserSerializer



class EventSubtaskListCreateView(ListCreateAPIView):
    serializer_class = SubtaskSerializer

    @extend_schema(
        summary="List or create subtasks for a specific event",
        parameters=[
            OpenApiParameter(
                name="eid",     
                type=int, 
                location=OpenApiParameter.PATH, 
                description="ID of the parent event"
            )
        ],
        tags=["Subtasks"],
        examples=[
                    OpenApiExample(
                        "Valid Subtask Payload",
                        summary="Example of a valid subtask request",
                        value={
                            "name": "Review Sprint Documentation",
                            "status": "PENDIENTE",
                            "due_date": "2026-10-15"
                        },
                        request_only=True,
                    )
                ]
    )
    def get(self): #GET: Only return subtasks belonging to the event id in URL
        event_id = self.kwargs['eid']
        return Subtasks.objects.filter(eid=event_id)

    @extend_schema(
        summary="Create a new subtask",
        description="""
        Creates a new subtask associated with a specific event.
        
        * **Note:** The `due_date` must be set in the future.
        * **Permissions:** Requires an authenticated user.
        """,
        tags=["Subtasks"],  # Groups endpoints together in Swagger UI
        request=SubtaskSerializer,
        responses={
            201: SubtaskSerializer,
            400: OpenApiResponse(description="Validation error (e.g., past due date or invalid enum value)"),
            404: OpenApiResponse(description="Parent Event not found"),
        },
        examples=[
            OpenApiExample(
                "Valid Subtask Payload",
                summary="Example of a valid subtask request",
                value={
                    "name": "Review Sprint Documentation",
                    "status": "PENDIENTE",
                    "due_date": "2026-10-15"
                },
                request_only=True,
            )
        ]
    )
    def post(self, serializer): #POST: Attaches to specific event
        event = get_object_or_404(Events, pk=self.kwargs['eid'])
        serializer.save(eid=event)