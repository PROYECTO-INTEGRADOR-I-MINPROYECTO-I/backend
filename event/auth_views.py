from django.contrib.auth.hashers import check_password, make_password

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Users
from .serializers import LoginSerializer, UserRegisterSerializer, UserSerializer

# Hash "de mentira" para comparar contra él cuando el correo no existe: así
# check_password tarda lo mismo que con un usuario real y no delatamos por
# tiempo de respuesta si el correo está registrado o no.
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
    """Sin esto DRF convierte los 401 de AuthenticationFailed en 403,
    porque cree que no hay ningún esquema de auth disponible."""

    def get_authenticate_header(self, request):
        return "Session"


@extend_schema(
    summary="Iniciar sesión",
    description=(
        "Autentica al usuario con correo y contraseña e inicia sesión con una "
        "cookie. Correo inexistente y contraseña incorrecta responden igual. "
        "Máximo 5 intentos por minuto."
    ),
    tags=["Auth"],
    request=LoginSerializer,
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description="Falta el correo o la contraseña"),
        401: OpenApiResponse(description="Credenciales inválidas"),
        429: OpenApiResponse(description="Demasiados intentos"),
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

        user = Users.objects.filter(email__iexact=email).first()
        if user is None:
            # Igual costo que un login válido, para no filtrar si el correo existe.
            check_password(password, _dummy_hash())
            raise InvalidCredentials()

        if not check_password(password, user.password_hash):
            raise InvalidCredentials()

        request.session.cycle_key()
        request.session["user_id"] = user.user_id
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Cerrar sesión",
    description="Termina la sesión actual. Es idempotente: siempre responde 204.",
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
    summary="Usuario actual",
    description="Devuelve el usuario de la sesión activa.",
    tags=["Auth"],
    responses={200: UserSerializer, 401: OpenApiResponse(description="No hay sesión activa")},
)
class MeView(SessionAuthHeaderMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        user_id = request.session.get("user_id")
        if not user_id:
            raise InvalidCredentials()

        user = Users.objects.filter(pk=user_id).first()
        if user is None:
            # La sesión apunta a un usuario que ya no existe.
            request.session.flush()
            raise InvalidCredentials()

        return Response(UserSerializer(user).data)


@extend_schema_view(
    post=extend_schema(
        summary="Registrar usuario",
        description="Crea una cuenta nueva e inicia sesión.",
        tags=["Auth"],
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description="Datos inválidos o correo no disponible"),
        },
    ),
)
class RegisterView(CreateAPIView):
    queryset = Users.objects.all()
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
