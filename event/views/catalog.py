from django.db import IntegrityError, transaction
from django.db.models import Q

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import ListCreateAPIView

from ..exceptions import Conflict
from ..models import Category, EventType
from ..serializers import CategorySerializer, EventTypeSerializer
from .mixins import OrganizerMixin


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
