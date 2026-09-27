from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)  # No empty named user allowed
    max_daily_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=0.0,  # Prevents negative values
    )

    class Meta:
        model = User
        # Does not include password_hash: this serializer backs
        # GET/PATCH /api/yo/, and must never return the hash in the response.
        fields = ['user_id', 'name', 'email', 'max_daily_hours']


class UserRegisterSerializer(serializers.ModelSerializer):
    password_hash = serializers.CharField(
        write_only=True,          # <--- NEVER returned in JSON response!
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ['user_id', 'email', 'name', 'max_daily_hours', 'password_hash']

    def create(self, validated_data):
        validated_data['password_hash'] = make_password(validated_data['password_hash'])
        user = User.objects.create(
            name=validated_data['name'],
            email=validated_data.get('email', ''),
            password_hash=validated_data['password_hash'],
            max_daily_hours=validated_data['max_daily_hours'],
        )
        return user
