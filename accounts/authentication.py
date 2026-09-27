from rest_framework.authentication import BaseAuthentication

from .models import User


class OrganizerSessionAuthentication(BaseAuthentication):
    """Authenticates by reading the user_id stored in the session (cookie login).

    Doesn't use django.contrib.auth: User is our own model, so instead of
    AnonymousUser we return None when there's no valid session, and let the
    permission (IsOrganizer) decide whether that's enough to block the request.
    """

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
