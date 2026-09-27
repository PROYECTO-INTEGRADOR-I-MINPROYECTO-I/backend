from accounts.models import User


def get_current_organizer(request):
    """Returns the "current" organizer for the request.

    TODO(PIM1-91): this is a temporary stub until there's real authentication.
    The frontend (src/lib/demo-auth.ts) assumes a single demo user with this
    email; once real auth is implemented, this function should be replaced by
    resolving the authenticated user from the request.
    """
    organizer, _ = User.objects.get_or_create(
        email="demo@planificapp.com",
        defaults={
            "name": "Demo",
            "password_hash": "!unusable",
        },
    )
    return organizer
