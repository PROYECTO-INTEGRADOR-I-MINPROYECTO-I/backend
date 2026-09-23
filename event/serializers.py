from rest_framework import serializers
from .models import Tasks, Subtasks


# Event model serializer for parsing requests
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = '__all__' 

class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = '__all__' 
        read_only_fields = ['event']  # <--- ID will be assigned from URL parameter
