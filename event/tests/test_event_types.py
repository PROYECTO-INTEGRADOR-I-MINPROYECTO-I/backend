from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from event.models import Event, EventType


class EventTypeDeleteTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create(email="owner@email.com", password_hash=make_password("pass12345"))
        self.other = User.objects.create(email="other@email.com", password_hash=make_password("pass12345"))
        self.custom = EventType.objects.create(name="Retiro", user=self.owner)
        self.client.force_authenticate(user=self.owner)

    def url(self, event_type):
        return reverse("event:event-type-detail", kwargs={"event_type_id": event_type.pk})

    def test_owner_deletes_custom_type_and_event_keeps_no_type(self):
        event = Event.objects.create(
            name="Retiro anual", due_date=timezone.now() + timedelta(days=3), user=self.owner, event_type=self.custom
        )
        self.assertEqual(self.client.delete(self.url(self.custom)).status_code, 204)
        event.refresh_from_db()
        self.assertIsNone(event.event_type)

    def test_predefined_type_cannot_be_deleted(self):
        predefined = EventType.objects.create(name="Predefinido test", user=None)
        self.assertEqual(self.client.delete(self.url(predefined)).status_code, 404)
        self.assertTrue(EventType.objects.filter(pk=predefined.pk).exists())

    def test_cannot_delete_another_users_type(self):
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.delete(self.url(self.custom)).status_code, 404)

    def test_list_marks_custom_types(self):
        data = self.client.get(reverse("event:event-type-create")).json()
        self.assertTrue(next(t for t in data if t["name"] == "Retiro")["custom"])
