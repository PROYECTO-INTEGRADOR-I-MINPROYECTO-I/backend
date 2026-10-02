from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models import User

NEUTRAL_MESSAGE = "Inicia sesión para continuar."


class OrganizerJWTAuthentication(JWTAuthentication):
    """Bearer JWT auth over our own User model (not django.contrib.auth)."""

    def authenticate(self, request):
        try:
            result = super().authenticate(request)
        except (InvalidToken, TokenError):
            # Tampered, expired or wrong-type tokens: same neutral 401 as revoked.
            raise AuthenticationFailed(NEUTRAL_MESSAGE, code="authentication_failed")
        if result is None:
            return None

        user, _token = result
        request._request.organizer = user
        return result

    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")
        user = User.objects.filter(pk=user_id).first() if user_id is not None else None
        # A bumped token_version (logout) revokes every token issued before.
        if user is None or validated_token.get("ver") != user.token_version:
            raise AuthenticationFailed(NEUTRAL_MESSAGE, code="authentication_failed")
        return user

    def authenticate_header(self, request):
        # Needed so a missing auth translates into 401 instead of 403.
        return "Bearer"
