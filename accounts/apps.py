from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        # Registers the drf-spectacular extension for session auth.
        from . import schema  # noqa: F401
