from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("event.urls")),
]

# El admin de Django solo se registra en local (DEBUG activo);
# el backend desplegado es API-only.
if settings.DEBUG:
    urlpatterns.append(path("admin/", admin.site.urls))
