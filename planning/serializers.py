from rest_framework import serializers

from event.serializers import SubtaskSerializer


class TodaySubtaskSerializer(SubtaskSerializer):
    # Read-only: used in /api/today/, not for creation/edition.
    event_name = serializers.CharField(source="eid.name", read_only=True)

    class Meta(SubtaskSerializer.Meta):
        fields = SubtaskSerializer.Meta.fields + ["event_name"]


class DayProgressSerializer(serializers.Serializer):
    # Only to document the shape of "day_progress" in Swagger.
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    completed_hours = serializers.DecimalField(max_digits=6, decimal_places=2)
    total_hours = serializers.DecimalField(max_digits=6, decimal_places=2)
