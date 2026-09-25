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