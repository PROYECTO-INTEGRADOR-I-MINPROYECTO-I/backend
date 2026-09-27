import datetime

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Event, EventType


# Date validator function
def validate_future_date(value):
    # Extract just the date part for comparison
    today = timezone.now().date()

    # Handle both date and datetime instances passed to the validator
    check_date = value.date() if isinstance(value, datetime.datetime) else value

    if check_date < today:
        raise ValidationError("La fecha debe ser hoy o posterior.")
    return value


# Event model serializer for parsing requests
class EventSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            "blank": "Escribe el nombre del evento.",
            "required": "Escribe el nombre del evento.",
        },
    )
    due_date = serializers.DateTimeField(
        validators=[validate_future_date],
        error_messages={
            "required": "Elige la fecha del evento.",
            "invalid": "La fecha del evento no es válida.",
        },
    )
    event_type = serializers.PrimaryKeyRelatedField(
        queryset=EventType.objects.all(),
        allow_null=True,
        required=False,
        error_messages={
            "does_not_exist": "El tipo de evento no existe.",
            "incorrect_type": "El tipo de evento no es válido.",
        },
    )
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "eid",
            "user",
            "name",
            "description",
            "due_date",
            "event_type",
            "place",
            "client_contact",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["eid", "user", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organizer = self.context.get("organizer")
        if organizer is not None:
            self.fields["event_type"].queryset = EventType.objects.filter(
                Q(user__isnull=True) | Q(user=organizer)
            )

    def validate_name(self, value):
        if not value.strip():
            raise ValidationError("Escribe el nombre del evento.")
        return value
