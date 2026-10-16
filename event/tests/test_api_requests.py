from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from event.models import Category, Event, EventType, Subtask


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


class SubtaskRequestTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            name="Ana",
            email="ana@example.com",
            password_hash=make_password("securepassword123"),
        )
        self.event = Event.objects.create(
            user=self.user,
            name="Boda de Ana",
            due_date=timezone.now() + timedelta(days=30),
        )
        self.category = Category.objects.filter(user__isnull=True).first()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("event:event-subtasks", kwargs={"eid": self.event.pk})

    def test_incomplete_subtask_request_returns_required_field_errors(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        details = response.data["error"]["details"]
        for field in ("title", "category", "estimated_hours", "scheduled_date"):
            self.assertIn(field, details)

    def test_valid_subtask_request_returns_created_subtask(self):
        scheduled_date = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(
            self.url,
            {
                "title": "Cotizar catering",
                "description": "Solicitar tres cotizaciones",
                "category": self.category.name,
                "estimated_hours": 2,
                "scheduled_date": scheduled_date,
                "status": "pending",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Cotizar catering")
        self.assertEqual(response.data["category"], self.category.name)
        self.assertEqual(response.data["eid"], self.event.pk)
        self.assertEqual(response.data["scheduled_date"], scheduled_date)
        self.assertEqual(Subtask.objects.filter(eid=self.event).count(), 1)


class CatalogRequestTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            name="Ana",
            email="ana@example.com",
            password_hash=make_password("securepassword123"),
        )
        self.client.force_authenticate(user=self.user)

    def test_incomplete_event_type_request_returns_name_error(self):
        response = self.client.post(
            reverse("event:event-type-create"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data["error"]["details"])

    def test_valid_event_type_request_returns_created_type(self):
        response = self.client.post(
            reverse("event:event-type-create"),
            {"name": "Conferencia"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Conferencia")
        self.assertIsNotNone(response.data["id"])
        self.assertTrue(
            EventType.objects.filter(name="Conferencia", user=self.user).exists()
        )

    def test_incomplete_category_request_returns_name_error(self):
        response = self.client.post(
            reverse("event:category-create"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data["error"]["details"])

    def test_valid_category_request_returns_created_category(self):
        response = self.client.post(
            reverse("event:category-create"),
            {"name": "Decoración"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {"id": "Decoración", "name": "Decoración"})
        self.assertTrue(
            Category.objects.filter(name="Decoración", user=self.user).exists()
        )