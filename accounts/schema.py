from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OrganizerJWTScheme(OpenApiAuthenticationExtension):
    # Documents the Bearer JWT auth for Swagger / /api/docs/.
    target_class = "accounts.authentication.OrganizerJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
