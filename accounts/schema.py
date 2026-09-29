from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OrganizerSessionScheme(OpenApiAuthenticationExtension):
    # Documents the session cookie auth for Swagger / /api/docs/.
    target_class = "accounts.authentication.OrganizerSessionAuthentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
