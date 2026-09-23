from rest_framework import serializers
from .models import Events, Subtasks


# Event model serializer for parsing requests
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = '__all__' 

class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtasks
        fields = '__all__' 
        read_only_fields = ['eid']  # Event ID assigned from URL parameter
