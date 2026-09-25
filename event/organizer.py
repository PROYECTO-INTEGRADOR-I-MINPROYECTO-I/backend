from .models import Users


def get_current_organizer(request):
    """Devuelve el organizador "actual" para la request.

    TODO(PIM1-91): esto es un stub temporal mientras no hay autenticación.
    El front (src/lib/demo-auth.ts) asume un único usuario demo con este
    correo; cuando se implemente auth real, esta función debe reemplazarse
    por la resolución del usuario autenticado a partir de la request.
    """
    organizer, _ = Users.objects.get_or_create(
        email="demo@planificapp.com",
        defaults={
            "name": "Demo",
            "password_hash": "!unusable",
        },
    )
    return organizer
