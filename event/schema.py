from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OrganizerSessionScheme(OpenApiAuthenticationExtension):
    # Le dice a Swagger que la API se autentica con la cookie de sesión.
    # Tras hacer login desde /api/docs/ el navegador ya manda la cookie.
    target_class = "event.authentication.OrganizerSessionAuthentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
