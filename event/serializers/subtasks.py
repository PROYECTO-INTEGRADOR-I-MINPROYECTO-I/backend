from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..models import Category, Subtask


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
        choices=Subtask.STATUS_CHOICES,
        required=False,
        error_messages={"invalid_choice": "El estado no es válido."},
    )

    class Meta:
        model = Subtask
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
