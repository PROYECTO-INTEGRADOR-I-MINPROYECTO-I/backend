import datetime

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from planning.services import event_progress

from ..models import Event, EventType


def validate_future_date(value):
    # localdate() and not now().date(): with TIME_ZONE in America/Bogota,
    # using now() in UTC runs the server's "today" several hours off from
    # the organizer's (same bug the TIME_ZONE setting fixes).
    today = timezone.localdate()

    # value can be a date or a datetime; only the date part matters here.
    check_date = value.date() if isinstance(value, datetime.datetime) else value

    if check_date < today:
        raise ValidationError("La fecha debe ser hoy o posterior.")
    return value


class EventProgressSerializer(serializers.Serializer):
    # Only to document the shape of "progress" in Swagger.
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    percentage = serializers.IntegerField()


class EventSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=150,
        error_messages={
            "blank": "Escribe el nombre del evento.",
            "required": "Escribe el nombre del evento.",
            "max_length": "El nombre del evento no puede superar los 150 caracteres.",
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
    # Progress (done/total) of the event's subtasks; see services.event_progress.
    progress = serializers.SerializerMethodField()

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
            "progress",
        ]
        read_only_fields = ["eid", "user", "created_at", "updated_at", "progress"]

    @extend_schema_field(EventProgressSerializer)
    def get_progress(self, obj):
        return event_progress(obj)

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
