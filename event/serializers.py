from rest_framework import serializers
from .models import Events, Subtasks, Users
from django.utils import timezone
from rest_framework.exceptions import ValidationError
import datetime

#----------------GLOBAL VALIDATION FUNCTIONS------------------

# Date Validator function
def validate_future_date(value):
    # Extract just the date part for comparison
    today = timezone.now().date()
    
    # Handle both date and datetime instances passed to the validator
    check_date = value.date() if isinstance(value, datetime.datetime) else value
    
    if check_date < today:
        raise ValidationError("The date must be in the future.")
    return value

# Event model serializer for parsing requests
class EventSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False) #No empty named events allowed
    progress_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        min_value=0.0,  #Prevents negative values
        max_value=100.0 #Prevents percentage over 100
    )
    status = serializers.ChoiceField(
        choices=["PROXIMA", "PENDIENTE", "COMPLETADA", "VENCIDA"]
    )
    due_date = serializers.DateField(validators=[validate_future_date])
    class Meta:
        model = Events
        fields = '__all__' 

class SubtaskSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=True, allow_blank=False)
    estimated_hours = serializers.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        min_value=0.0  #Prevents negative values
    )
    scheduled_date = serializers.DateField(validators=[validate_future_date])
    priority = serializers.ChoiceField(
            choices=['low', 'medium', 'high', 'urgent']
        )
    class Meta:
        model = Subtasks
        fields = '__all__' 
        read_only_fields = ['eid']  # Event ID assigned from URL parameter


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False) #No empty named user allowed
    max_daily_hours = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        min_value=0.0,  #Prevents negative values
    )
    class Meta:
        model = Users
        fields = '__all__' 
