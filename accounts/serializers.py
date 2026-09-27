from decimal import Decimal

from django.contrib.auth import password_validation
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import User


class LoginSerializer(serializers.Serializer):
    # Only documents the login body in Swagger; the actual validation lives in the view.
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)  # No empty named user allowed
    # Read-only: the daily limit changes through /api/user/settings/.
    max_daily_hours = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)

    class Meta:
        model = User
        # Does not include password_hash: this serializer backs auth
        # endpoints, and must never return the hash in the response.
        fields = ['user_id', 'name', 'email', 'max_daily_hours']


class UserSettingsSerializer(serializers.ModelSerializer):
    max_daily_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("1"),
        max_value=Decimal("16"),
        error_messages={
            "required": "El límite debe estar entre 1 y 16 horas",
            "min_value": "El límite debe estar entre 1 y 16 horas",
            "max_value": "El límite debe estar entre 1 y 16 horas",
            "invalid": "El límite debe ser un número.",
        },
    )

    class Meta:
        model = User
        fields = ['max_daily_hours']


class UserRegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            "blank": "Escribe tu nombre.",
            "required": "Escribe tu nombre.",
        },
    )
    email = serializers.EmailField(
        required=True,
        error_messages={
            "required": "Escribe tu correo.",
            "invalid": "El correo no es válido.",
        },
    )
    password = serializers.CharField(
        write_only=True,          # <--- NEVER returned in JSON response!
        required=True,
        min_length=8,
        style={'input_type': 'password'},
        error_messages={
            "required": "Escribe tu contraseña.",
            "min_length": "La contraseña debe tener al menos 8 caracteres.",
        },
    )

    class Meta:
        model = User
        fields = ['user_id', 'email', 'name', 'max_daily_hours', 'password']

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            # Neutral message: we don't confirm the email is already registered.
            raise ValidationError("No se pudo completar el registro con esos datos.")
        return value

    def validate_password(self, value):
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create(
            name=validated_data['name'],
            email=validated_data['email'],
            password_hash=make_password(password),
            **({'max_daily_hours': validated_data['max_daily_hours']} if 'max_daily_hours' in validated_data else {}),
        )
        return user
