from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny

from event.views.mixins import OrganizerMixin

from .models import User
from .serializers import UserRegisterSerializer, UserSerializer


@extend_schema_view(
    get=extend_schema(
        summary="Get current organizer",
        description="Returns the current organizer (the same one resolved by get_current_organizer).",
        tags=["Usuarios"],
    ),
    patch=extend_schema(
        summary="Update current organizer",
        description="Updates one or more fields of the current organizer (e.g. max_daily_hours).",
        tags=["Usuarios"],
    ),
)
class CurrentUserView(OrganizerMixin, RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]  # No login yet (PIM1-91): a single demo organizer.

    def get_object(self):
        # This method used to have its own get_or_create(email="demo@example.com"),
        # which created a second organizer different from the one used by
        # EventListCreateView/EventSubtaskListCreateView/etc. (get_current_organizer,
        # "demo@planificapp.com" in organizer.py). Unified into a single source of
        # truth: what /api/yo/ returns is always the same organizer that owns the
        # events and subtasks created.
        return self.get_organizer()


@extend_schema_view(
    post=extend_schema(
        summary="Register a new user.",
        description="Creates a new user registry.",
        tags=["Usuarios"],
    ),
)
class UserRegisterView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]  # Allow any user to register
