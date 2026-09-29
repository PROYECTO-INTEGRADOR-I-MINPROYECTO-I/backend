import datetime
import re

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Event, EventType

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_future_date(value):
    # localdate(), not now().date(): keeps "today" in America/Bogota, not UTC.
    today = timezone.localdate()

    # value can be a date or a datetime; only the date part matters here.
    check_date = value.date() if isinstance(value, datetime.datetime) else value

    if check_date < today:
        raise ValidationError("La fecha debe ser hoy o posterior.")
    return value


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
    cover_kind = serializers.ChoiceField(
        choices=Event.COVER_KIND_CHOICES,
        allow_null=True,
        required=False,
        error_messages={"invalid_choice": "El tipo de portada no es válido."},
    )
    cover_value = serializers.CharField(
        allow_null=True,
        allow_blank=True,
        required=False,
        max_length=500,
        error_messages={"max_length": "El valor de la portada no puede superar los 500 caracteres."},
    )

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
            "cover_kind",
            "cover_value",
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

    def validate(self, attrs):
        # En un PATCH parcial, attrs solo trae los campos que llegaron en el
        # body; para validar la pareja completa hay que completar con lo que
        # ya tiene la instancia cuando no se está enviando ese campo.
        if self.instance is not None:
            kind = attrs.get("cover_kind", self.instance.cover_kind)
            value = attrs.get("cover_value", self.instance.cover_value)
        else:
            kind = attrs.get("cover_kind")
            value = attrs.get("cover_value")

        value = value or None  # "" cuenta como "sin portada", igual que None.

        if bool(kind) != bool(value):
            raise ValidationError(
                {"cover_value": "cover_kind y cover_value deben ir juntos, o ninguno de los dos."}
            )

        if kind == "color" and value and not HEX_COLOR_PATTERN.match(value):
            raise ValidationError({"cover_value": "El color debe ser un hexadecimal válido, por ejemplo #8b1a1a."})

        # Normaliza "" a None y guarda el valor ya completado (para que un
        # PATCH que solo manda uno de los dos campos no deje el otro con un
        # valor viejo inconsistente).
        if "cover_kind" in attrs or "cover_value" in attrs:
            attrs["cover_kind"] = kind
            attrs["cover_value"] = value

        return attrs
