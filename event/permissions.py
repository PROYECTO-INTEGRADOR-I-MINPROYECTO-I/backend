from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from .models import Users


class IsOrganizador(BasePermission):
    """Exige un organizador autenticado por sesión (event.authentication)."""

    message = "Inicia sesión para continuar."

    def has_permission(self, request, view):
        if isinstance(request.user, Users):
            return True
        # Mismo mensaje tanto si no hay sesión como si el auth falló, para
        # no dar pistas de por qué exactamente no pasó.
        raise NotAuthenticated(self.message)
