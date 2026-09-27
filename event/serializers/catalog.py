from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..exceptions import Conflict
from ..models import Category, EventType


class EventTypeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="event_type_id", read_only=True)
    name = serializers.CharField(required=True, allow_blank=True)

    class Meta:
        model = EventType
        fields = ["id", "name"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise ValidationError("Escribe el nombre del tipo de evento.")

        organizer = self.context.get("organizer")
        duplicates = EventType.objects.filter(name__iexact=value).filter(
            Q(user__isnull=True) | Q(user=organizer)
        )
        if duplicates.exists():
            raise Conflict("Ya tienes un tipo de evento con ese nombre")
        return value


class CategorySerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="name", read_only=True)
    name = serializers.CharField(required=True, allow_blank=True)

    class Meta:
        model = Category
        fields = ["id", "name"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise ValidationError("Escribe el nombre de la categoría.")

        organizer = self.context.get("organizer")
        duplicates = Category.objects.filter(name__iexact=value).filter(
            Q(user__isnull=True) | Q(user=organizer)
        )
        if duplicates.exists():
            raise Conflict("Ya tienes una categoría con ese nombre")
        return value
