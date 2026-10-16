from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from event.models import Event


class EventRequestTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            name="Ana",
            email="ana@example.com",
            password_hash=make_password("securepassword123"),
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("event:event-create")

    def test_incomplete_event_request_returns_required_field_errors(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        details = response.data["error"]["details"]
        self.assertIn("name", details)
        self.assertIn("due_date", details)

    def test_valid_event_request_returns_created_event(self):
        response = self.client.post(
            self.url,
            {
                "name": "Boda de Ana",
                "description": "Evento familiar",
                "due_date": (timezone.now() + timedelta(days=30)).isoformat(),
                "place": "Salón principal",
                "client_contact": "555-0101",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Boda de Ana")
        self.assertEqual(response.data["description"], "Evento familiar")
        self.assertEqual(response.data["user"], self.user.pk)
        self.assertIsNotNone(response.data["eid"])
        self.assertTrue(Event.objects.filter(name="Boda de Ana", user=self.user).exists())
