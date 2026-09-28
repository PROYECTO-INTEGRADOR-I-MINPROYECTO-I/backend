from rest_framework import serializers

from event.serializers import SubtaskSerializer


class TodaySubtaskSerializer(SubtaskSerializer):
    # Read-only: used in /api/hoy/, not for creation/edition.
    event_name = serializers.CharField(source="eid.name", read_only=True)

    class Meta(SubtaskSerializer.Meta):
        fields = SubtaskSerializer.Meta.fields + ["event_name"]


class DayProgressSerializer(serializers.Serializer):
    # Maps day_progress's English keys (from services.py) to the Spanish
    # keys the "progreso_dia" contract requires.
    completadas = serializers.IntegerField(source="completed")
    total = serializers.IntegerField()
    horas_completadas = serializers.DecimalField(
        source="completed_hours", max_digits=6, decimal_places=2
    )
    horas_totales = serializers.DecimalField(
        source="total_hours", max_digits=6, decimal_places=2
    )
