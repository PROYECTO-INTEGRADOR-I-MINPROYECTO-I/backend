class OrganizerMixin:
    """Exposes the authenticated organizer (request.user) to the serializer."""

    def get_organizer(self):
        return self.request.user

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organizer"] = self.get_organizer()
        return context
