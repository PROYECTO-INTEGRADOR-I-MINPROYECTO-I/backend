from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("api/", include("event.urls")),
    # OpenAPI 3 Schema generation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Interactive Swagger UI:
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # Optional ReDoc UI:
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# El admin de Django solo se registra en local (DEBUG activo);
# el backend desplegado es API-only.
if settings.DEBUG:
    urlpatterns.append(path("admin/", admin.site.urls))
