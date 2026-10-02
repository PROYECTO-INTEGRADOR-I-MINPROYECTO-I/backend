import time

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import F

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import AuthTokenSerializer, LoginSerializer, UserRegisterSerializer, UserSerializer
from .authentication import OrganizerJWTAuthentication
from .tokens import issue_tokens

# Hash to check against when the email doesn't exist.
_DUMMY_PASSWORD_HASH = None


def _dummy_hash():
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = make_password("clave-que-nunca-se-usa")
    return _DUMMY_PASSWORD_HASH


class BearerAuthHeaderMixin:
    """Views without authenticators need this, or DRF turns 401s into 403s."""

    def get_authenticate_header(self, request):
        return "Bearer"


class InvalidCredentials(AuthenticationFailed):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Credenciales inválidas"
    default_code = "authentication_failed"


REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth/"
NOT_AUTHENTICATED_MESSAGE = "Inicia sesión para continuar."

_LOGIN_RESPONSE_DESCRIPTION = (
    "Body {user, access}; the refresh token travels in the HttpOnly "
    "'refresh_token' cookie."
)


def _cookie_secure():
    # Secure/SameSite=None outside local dev, even if DEBUG is on by mistake.
    return not settings.DEBUG or settings.ENVIRONMENT != "dev"


def _cookie_samesite():
    return "None" if _cookie_secure() else "Lax"


def _set_refresh_cookie(response, refresh):
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path=REFRESH_COOKIE_PATH,
    )


def _delete_refresh_cookie(response):
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        samesite=_cookie_samesite(),
    )


def _auth_response(user, status_code, auth_time=None):
    """Build the {user, access} response and set the refresh cookie."""
    refresh, access = issue_tokens(user, auth_time=auth_time)
    response = Response(
        {"user": UserSerializer(user).data, "access": access}, status=status_code
    )
    _set_refresh_cookie(response, refresh)
    return response


def _origin_allowed(request):
    """CSRF defense for the refresh cookie: a present Origin must be allowed."""
    origin = request.headers.get("Origin")
    if origin is None:
        return True
    allowed = {o.rstrip("/") for o in settings.CORS_ALLOWED_ORIGINS}
    return origin.rstrip("/") in allowed


def _forbidden_origin():
    return Response(
        {"detail": "Origen no permitido."}, status=status.HTTP_403_FORBIDDEN
    )


def _user_from_refresh_cookie(request):
    """Return (user, token) behind a valid refresh cookie, or (None, None)."""
    raw = request.COOKIES.get(REFRESH_COOKIE)
    if not raw:
        return None, None
    try:
        token = RefreshToken(raw)
    except TokenError:
        return None, None

    user_id = token.get("user_id")
    if user_id is None:
        return None, None
    user = User.objects.filter(pk=user_id).first()
    if user is None or token.get("ver") != user.token_version:
        return None, None
    return user, token


def _user_from_bearer(request):
    """Return the user behind a valid Bearer access token, or None."""
    try:
        result = OrganizerJWTAuthentication().authenticate(request)
    except AuthenticationFailed:
        return None
    return result[0] if result else None


def _within_session_cap(token):
    """The original login (auth_time) must be younger than JWT_MAX_SESSION_DAYS."""
    auth_time = token.get("auth_time")
    if not isinstance(auth_time, int):
        return False
    return time.time() - auth_time <= settings.JWT_MAX_SESSION_DAYS * 86400


@extend_schema(
    summary="Log in",
    description=(
        "Authenticates the user with email and password and returns a short-lived "
        "access token. A nonexistent email and a wrong password respond the same "
        "way. " + _LOGIN_RESPONSE_DESCRIPTION
    ),
    tags=["Auth"],
    request=LoginSerializer,
    responses={
        200: AuthTokenSerializer,
        400: OpenApiResponse(description="Missing email or password"),
        401: OpenApiResponse(description="Invalid credentials"),
    },
)
class LoginView(BearerAuthHeaderMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email:
            raise ValidationError({"email": ["Escribe tu correo."]})
        if not password:
            raise ValidationError({"password": ["Escribe tu contraseña."]})

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            # Same cost as a real login: timing doesn't leak the email.
            check_password(password, _dummy_hash())
            raise InvalidCredentials()

        if not check_password(password, user.password_hash):
            raise InvalidCredentials()

        return _auth_response(user, status.HTTP_200_OK)


@extend_schema(
    summary="Log out",
    description=(
        "If the refresh cookie or the Bearer access token is valid, revokes every "
        "access and refresh token of the user. Always clears the cookie. Idempotent: always responds 204."
    ),
    tags=["Auth"],
    request=None,
    responses={
        204: None,
        403: OpenApiResponse(description="Origin not allowed"),
    },
)
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _origin_allowed(request):
            return _forbidden_origin()

        user, _token = _user_from_refresh_cookie(request)
        if user is None:
            user = _user_from_bearer(request)
        if user is not None:
            # Atomic bump: invalidates all tokens issued with the old version.
            User.objects.filter(pk=user.pk).update(token_version=F("token_version") + 1)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _delete_refresh_cookie(response)
        return response


@extend_schema(
    summary="Refresh the access token",
    description=(
        "Reads the 'refresh_token' cookie, rotates it and returns a new access "
        "token. Without a valid cookie, or once the session is older than "
        "JWT_MAX_SESSION_DAYS, it responds 401 and clears it."
    ),
    tags=["Auth"],
    request=None,
    responses={
        200: AuthTokenSerializer,
        401: OpenApiResponse(description="Missing, invalid or revoked refresh token"),
        403: OpenApiResponse(description="Origin not allowed"),
    },
)
class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _origin_allowed(request):
            return _forbidden_origin()

        user, token = _user_from_refresh_cookie(request)
        if user is None or not _within_session_cap(token):
            response = Response(
                {"detail": NOT_AUTHENTICATED_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _delete_refresh_cookie(response)
            return response

        # Keep the original auth_time so rotation can't extend the session forever.
        return _auth_response(user, status.HTTP_200_OK, auth_time=token["auth_time"])


@extend_schema(
    summary="Current user",
    description="Returns the authenticated user (Bearer access token).",
    tags=["Auth"],
    responses={200: UserSerializer, 401: OpenApiResponse(description="Missing, invalid or revoked access token")},
)
class MeView(APIView):
    # Uses the default authentication and permission (Bearer JWT + IsOrganizer).

    def get(self, request):
        return Response(UserSerializer(request.user).data)


@extend_schema_view(
    post=extend_schema(
        summary="Register a user",
        description="Creates a new account. " + _LOGIN_RESPONSE_DESCRIPTION,
        tags=["Auth"],
        responses={
            201: AuthTokenSerializer,
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

        return _auth_response(user, status.HTTP_201_CREATED)
