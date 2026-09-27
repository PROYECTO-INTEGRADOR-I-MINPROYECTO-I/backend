from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OrganizerSessionScheme(OpenApiAuthenticationExtension):
    # Tells Swagger the API authenticates with the session cookie.
    # After logging in from /api/docs/ the browser already sends the cookie.
    target_class = "accounts.authentication.OrganizerSessionAuthentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
