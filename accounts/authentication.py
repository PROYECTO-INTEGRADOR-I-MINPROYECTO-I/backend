from rest_framework.authentication import BaseAuthentication

from .models import User


class OrganizerSessionAuthentication(BaseAuthentication):
    """Session-based auth over our own User model (not django.contrib.auth)."""

    def authenticate(self, request):
        user_id = request._request.session.get("user_id")
        if not user_id:
            return None

        user = User.objects.filter(pk=user_id).first()
        if user is None:
            # The session points to a deleted user: clean it up.
            request._request.session.flush()
            return None

        request._request.organizer = user
        return (user, None)

    def authenticate_header(self, request):
        # Needed so a missing auth translates into 401 instead of 403.
        return "Session"
