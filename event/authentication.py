from rest_framework.authentication import BaseAuthentication

from .models import Users


class OrganizerSessionAuthentication(BaseAuthentication):
    """Autentica leyendo el user_id guardado en la sesión (login con cookie).

    No usa django.contrib.auth: Users es un modelo propio, así que en vez de
    AnonymousUser devolvemos None cuando no hay sesión válida, y dejamos que
    el permiso (IsOrganizador) decida si eso basta para bloquear la request.
    """

    def authenticate(self, request):
        user_id = request._request.session.get("user_id")
        if not user_id:
            return None

        user = Users.objects.filter(pk=user_id).first()
        if user is None:
            # La sesión quedó apuntando a un usuario borrado: la limpiamos.
            request._request.session.flush()
            return None

        request._request.organizador = user
        return (user, None)

    def authenticate_header(self, request):
        # Necesario para que la falta de auth se traduzca en 401 y no en 403.
        return "Session"
