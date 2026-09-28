from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def test(request):
    return JsonResponse({
        "message": "Server is working!"
    })


def health(request):
    """Render's health check; 503 if the DB is unreachable, not just alive."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {
                "status": "unhealthy",
                "environment": settings.ENVIRONMENT,
                "database": "error",
                # Detail only in dev: don't leak infra info on a public endpoint.
                "detail": str(exc) if settings.DEBUG else None,
            },
            status=503,
        )

    return JsonResponse({
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "database": "ok",
    })
