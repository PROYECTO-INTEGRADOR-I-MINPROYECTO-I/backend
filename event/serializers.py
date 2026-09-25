from rest_framework import serializers
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
import datetime

from .models import Events, Subtasks, Users, EventType, Category
from .exceptions import Conflict

#----------------GLOBAL VALIDATION FUNCTIONS------------------

# Date Validator function
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
        model = Events
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


class SubtaskSerializer(serializers.ModelSerializer):
    title = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            "blank": "Escribe el nombre de la gestión.",
            "required": "Escribe el nombre de la gestión.",
        },
    )
    category = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Category.objects.all(),
        error_messages={
            "required": "Elige una categoría.",
            "null": "Elige una categoría.",
            "does_not_exist": "La categoría no existe.",
            "invalid": "La categoría no es válida.",
        },
    )
    estimated_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        error_messages={
            "required": "Indica las horas estimadas.",
            "invalid": "Las horas estimadas deben ser un número.",
            "max_digits": "Las horas estimadas deben ser menores a 100.",
            "max_whole_digits": "Las horas estimadas deben ser menores a 100.",
            "max_decimal_places": "Usa como máximo 2 decimales en las horas estimadas.",
        },
    )
    scheduled_date = serializers.DateField(
        error_messages={
            "required": "Elige la fecha objetivo.",
            "invalid": "La fecha objetivo no es válida.",
        },
    )
    status = serializers.ChoiceField(
        choices=Subtasks.STATUS_CHOICES,
        required=False,
        error_messages={"invalid_choice": "El estado no es válido."},
    )

    class Meta:
        model = Subtasks
        fields = [
            "subtask_id",
            "eid",
            "title",
            "description",
            "category",
            "estimated_hours",
            "scheduled_date",
            "status",
            "postpone_note",
            "executed_at",
            "created_at",
        ]
        # eid comes from the URL; executed_at is stamped by the view on status changes.
        read_only_fields = ["eid", "executed_at", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organizer = self.context.get("organizer")
        if organizer is not None:
            self.fields["category"].queryset = Category.objects.filter(
                Q(user__isnull=True) | Q(user=organizer)
            )

    def validate_title(self, value):
        if not value.strip():
            raise ValidationError("Escribe el nombre de la gestión.")
        return value

    def validate_estimated_hours(self, value):
        if value <= 0:
            raise ValidationError("Las horas estimadas deben ser mayores a 0.")
        return value


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)  # No empty named user allowed
    max_daily_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=0.0,  # Prevents negative values
    )

    class Meta:
        model = Users
        # No incluye password_hash: este serializer es el que expone
        # GET/PATCH /api/yo/, y nunca debe devolver el hash en la respuesta.
        fields = ['user_id', 'name', 'email', 'max_daily_hours']


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,          # <--- NEVER returned in JSON response!
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = Users
        fields = '__all__'

    def create(self, validated_data):
        # Must use create_user() so Django hashes the password properly!
        user = Users.objects.create_user(
            name=validated_data['name'],
            email=validated_data.get('email', ''),
            password_hash=validated_data['password_hash'],
            max_daily_hours=validated_data['max_daily_hours'],
        )
        return user


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
