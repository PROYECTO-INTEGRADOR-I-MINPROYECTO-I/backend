from django.contrib.auth import password_validation
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import User


class LoginSerializer(serializers.Serializer):
    # Swagger only; the view validates.
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)  # No empty named user allowed
    # Read-only here: it is edited through UserSettingsSerializer.
    max_daily_hours = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)

    class Meta:
        model = User
        # No password_hash here: it must never reach a JSON response.
        fields = ['user_id', 'name', 'email', 'max_daily_hours']


class UserSettingsSerializer(serializers.ModelSerializer):
    max_daily_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=1,
        max_value=16,
        error_messages={
            "required": "Escribe el límite diario de horas.",
            "null": "Escribe el límite diario de horas.",
            "invalid": "El límite debe ser un número válido.",
            "min_value": "El límite debe estar entre 1 y 16 horas",
            "max_value": "El límite debe estar entre 1 y 16 horas",
            "max_digits": "El límite debe estar entre 1 y 16 horas",
            "max_decimal_places": "El límite admite máximo 2 decimales.",
            "max_whole_digits": "El límite debe estar entre 1 y 16 horas",
        },
    )

    class Meta:
        model = User
        # Only this field: anything else in the body is ignored.
        fields = ['max_daily_hours']

    def update(self, instance, validated_data):
        # Save only this column so a concurrent logout's token_version isn't overwritten.
        if 'max_daily_hours' in validated_data:
            instance.max_daily_hours = validated_data['max_daily_hours']
            instance.save(update_fields=['max_daily_hours'])
        return instance


class AuthTokenSerializer(serializers.Serializer):
    # Swagger only: shape of the login / register / refresh response.
    user = UserSerializer()
    access = serializers.CharField()


class UserRegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=100,
        error_messages={
            "blank": "Escribe tu nombre.",
            "required": "Escribe tu nombre.",
            "max_length": "El nombre no puede superar los 100 caracteres.",
        },
    )
    email = serializers.EmailField(
        required=True,
        max_length=150,
        error_messages={
            "required": "Escribe tu correo.",
            "invalid": "El correo no es válido.",
            "max_length": "El correo no puede superar los 150 caracteres.",
        },
    )
    password = serializers.CharField(
        write_only=True,
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
        # New accounts start with the model default (6h); it can't be set here.
        read_only_fields = ['user_id', 'max_daily_hours']

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
        )
        return user
