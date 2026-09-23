from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework.generics import ListCreateAPIView
from .models import Events, Subtasks
from .serializers import EventSerializer, SubtaskSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import ListCreateAPIView

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
class EventListCreateView(ListCreateAPIView):
    queryset = Events.objects.all()
    serializer_class = EventSerializer

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
        ]
    )

    #GET: Only return subtasks belonging to the event id in URL
    def get_queryset(self):
        event_id = self.kwargs['eid']
        return Subtask.objects.filter(eid=eid)

    # 2- POST: Attach the parent Event object automatically when saving
    def perform_create(self, serializer):
        event = get_object_or_404(Events, pk=self.kwargs['eid'])
        serializer.save(eid=event)