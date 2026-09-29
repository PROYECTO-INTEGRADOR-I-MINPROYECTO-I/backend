from ..organizer import get_current_organizer


class OrganizerMixin:
    """Resolves the "current" organizer (stub PIM1-91) and passes it to the serializer."""

    def get_organizer(self):
        # Cached per request: several hooks (context, queryset, save) need it.
        if not hasattr(self, "_organizer"):
            self._organizer = get_current_organizer(self.request)
        return self._organizer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organizer"] = self.get_organizer()
        return context
