from django.contrib.auth.hashers import check_password, make_password

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import User
from .serializers import (
    LoginSerializer,
    UserRegisterSerializer,
    UserSerializer,
    UserSettingsSerializer,
)

# Dummy hash to compare against when the email doesn't exist: this way
# check_password takes the same time as with a real user, and we don't leak
# through response time whether the email is registered.
_DUMMY_PASSWORD_HASH = None


def _dummy_hash():
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = make_password("clave-que-nunca-se-usa")
    return _DUMMY_PASSWORD_HASH


class InvalidCredentials(AuthenticationFailed):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Credenciales inválidas"
    default_code = "authentication_failed"


class SessionAuthHeaderMixin:
    """Without this DRF turns AuthenticationFailed 401s into 403s,
    because it thinks there's no auth scheme available."""

    def get_authenticate_header(self, request):
        return "Session"


@extend_schema(
    summary="Log in",
    description=(
        "Authenticates the user with email and password and starts a session "
        "cookie. A nonexistent email and a wrong password respond the same way. "
        "Max 5 attempts per minute."
    ),
    tags=["Auth"],
    request=LoginSerializer,
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description="Missing email or password"),
        401: OpenApiResponse(description="Invalid credentials"),
        429: OpenApiResponse(description="Too many attempts"),
    },
)
class LoginView(SessionAuthHeaderMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email:
            raise ValidationError({"email": ["Escribe tu correo."]})
        if not password:
            raise ValidationError({"password": ["Escribe tu contraseña."]})

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            # Same cost as a valid login, so we don't leak whether the email exists.
            check_password(password, _dummy_hash())
            raise InvalidCredentials()

        if not check_password(password, user.password_hash):
            raise InvalidCredentials()

        request.session.cycle_key()
        request.session["user_id"] = user.user_id
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Log out",
    description="Ends the current session. Idempotent: always responds 204.",
    tags=["Auth"],
    request=None,
    responses={204: None},
)
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        request.session.flush()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    summary="Current user",
    description="Returns the user of the active session.",
    tags=["Auth"],
    responses={200: UserSerializer, 401: OpenApiResponse(description="No active session")},
)
class MeView(APIView):
    # Uses the default authentication and permission (session + IsOrganizer).

    def get(self, request):
        return Response(UserSerializer(request.user).data)


@extend_schema_view(
    post=extend_schema(
        summary="Register a user",
        description="Creates a new account and starts a session.",
        tags=["Auth"],
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description="Invalid data or email not available"),
        },
    ),
)
class RegisterView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        request.session.cycle_key()
        request.session["user_id"] = user.user_id
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        summary="Get daily hours limit",
        description="Returns the current organizer's daily hours limit.",
        tags=["Usuarios"],
    ),
    put=extend_schema(
        summary="Replace daily hours limit",
        tags=["Usuarios"],
    ),
    patch=extend_schema(
        summary="Update daily hours limit",
        description="Updates the current organizer's daily hours limit (between 1 and 16).",
        tags=["Usuarios"],
    ),
)
class UserSettingsView(RetrieveUpdateAPIView):
    serializer_class = UserSettingsSerializer
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
