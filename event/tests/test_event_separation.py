from django.urls import reverse
from django.contrib.auth.hashers import make_password
from event.models import Event
from accounts.models import User
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient, APITestCase


class EventAccessTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        # Create two distinct users
        self.user_a = User.objects.create(
            email="usera@email.com",
            password_hash=make_password("securepasswordA123"),
        )
        self.user_b = User.objects.create(
            email="userb@email.com", password_hash=make_password("securepasswordB123")
        )

        # Create an event owned by User A
        self.event_a = Event.objects.create(
            name="User A's Private Event",
            due_date=timezone.now() + timedelta(days=1),
            user=self.user_a,
        )

    def test_user_cannot_view_another_users_event_detail(self):
        # Reverse using the 'events' namespace
        self.client.force_authenticate(user=self.user_b)
        url = reverse("event:event-detail", kwargs={"eid": self.event_a.pk})

        response = self.client.get(url)

        # Expect 404 (if filtered in get_queryset) or 403 (if using permission check)
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_see_another_users_events_in_list(self):
        self.client.force_authenticate(user=self.user_b)
        url = reverse("event:event-create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        returned_event_ids = [
            event["eid"] for event in response.data
        ]  # Use your ID key (eid, id, etc.)

        # Assert User A's event ID is NOT in the list
        self.assertNotIn(self.event_a.pk, returned_event_ids)
