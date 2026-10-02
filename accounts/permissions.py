from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from .models import User


class IsOrganizer(BasePermission):
    """Requires an organizer authenticated by session (accounts.authentication)."""

    message = "Inicia sesión para continuar."

    def has_permission(self, request, view):
        if isinstance(request.user, User):
            return True
        # Same message for no session or bad auth: don't hint why it failed.
        raise NotAuthenticated(self.message)
