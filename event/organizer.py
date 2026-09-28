from accounts.models import User


def get_current_organizer(request):
    """Stub organizer until real auth lands (PIM1-91)."""
    organizer, _ = User.objects.get_or_create(
        email="demo@planificapp.com",
        defaults={
            "name": "Demo",
            "password_hash": "!unusable",
        },
    )
    return organizer
