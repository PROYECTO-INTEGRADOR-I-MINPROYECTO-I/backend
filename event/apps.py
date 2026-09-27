from django.apps import AppConfig


class EventConfig(AppConfig):
    name = 'event'

    def ready(self):
        # Registra la extensión de drf-spectacular para la auth por sesión.
        from . import schema  # noqa: F401
