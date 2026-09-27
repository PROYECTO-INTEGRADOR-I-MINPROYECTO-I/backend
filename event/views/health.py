from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def test(request):
    return JsonResponse({
        "message": "Server is working!"
    })


def health(request):
    """Service health check.

    Render hits this endpoint to decide whether the deploy is healthy and to
    keep watching the service afterwards. A plain 200 isn't enough: if the
    app is alive but can't reach the database, it can't serve anything
    useful, so we also check the connection.

    Returns 200 if everything responds and 503 if the database doesn't
    answer, which is what Render treats as the service being down.
    """
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
                # Detail only in dev: in qa/prod it would leak infrastructure
                # data (host, user) on a public endpoint.
                "detail": str(exc) if settings.DEBUG else None,
            },
            status=503,
        )

    return JsonResponse({
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "database": "ok",
    })
