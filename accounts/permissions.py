from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from .models import User


class IsOrganizer(BasePermission):
    """Requires an organizer authenticated by session (accounts.authentication)."""

    message = "Inicia sesión para continuar."

    def has_permission(self, request, view):
        if isinstance(request.user, User):
            return True
        # Same message whether there's no session or auth failed, so we
        # don't give hints about the exact reason it didn't pass.
        raise NotAuthenticated(self.message)
