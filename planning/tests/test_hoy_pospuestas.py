from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from event.models import Category, Event, Subtask


class TodayPostponedTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            email="a@email.com", password_hash=make_password("securepasswordA123")
        )
        self.other = User.objects.create(
            email="b@email.com", password_hash=make_password("securepasswordB123")
        )
        self.category = Category.objects.filter(user__isnull=True).first()
        self.event = self.make_event(self.user, "A")
        self.today = timezone.localdate()
        self.client.force_authenticate(user=self.user)

    def make_event(self, user, name):
        return Event.objects.create(
            name=name, due_date=timezone.now() + timedelta(days=60), user=user
        )

    def make_subtask(self, day, status="postponed", event=None):
        return Subtask.objects.create(
            eid=event or self.event,
            title="Tarea",
            category=self.category,
            estimated_hours=Decimal("1"),
            scheduled_date=day,
            status=status,
        )

    def get_today(self, **params):
        return self.client.get(reverse("today"), params).json()

    def test_postponed_today_listed_not_in_pending(self):
        sub = self.make_subtask(self.today)
        data = self.get_today()
        self.assertEqual([s["subtask_id"] for s in data["para_hoy"]["pospuestas"]], [sub.pk])
        self.assertEqual(data["para_hoy"]["pendientes"], [])

    def test_other_days_are_counted_not_listed(self):
        self.make_subtask(self.today - timedelta(days=1))
        self.make_subtask(self.today + timedelta(days=1))
        data = self.get_today()
        self.assertEqual(data["pospuestas_otros_dias"], 2)
        self.assertEqual(data["para_hoy"]["pospuestas"], [])

    def test_event_id_filters_both(self):
        event_b = self.make_event(self.user, "B")
        self.make_subtask(self.today)
        self.make_subtask(self.today + timedelta(days=1))
        self.make_subtask(self.today, event=event_b)
        self.make_subtask(self.today - timedelta(days=1), event=event_b)
        self.make_subtask(self.today - timedelta(days=2), event=event_b)
        data = self.get_today(event_id=event_b.pk)
        self.assertEqual(len(data["para_hoy"]["pospuestas"]), 1)
        self.assertEqual(data["pospuestas_otros_dias"], 2)

    def test_other_user_not_counted(self):
        foreign = self.make_event(self.other, "X")
        self.make_subtask(self.today, event=foreign)
        self.make_subtask(self.today + timedelta(days=1), event=foreign)
        data = self.get_today()
        self.assertEqual(data["para_hoy"]["pospuestas"], [])
        self.assertEqual(data["pospuestas_otros_dias"], 0)

    def test_status_done_or_pending_empties_today_postponed(self):
        self.make_subtask(self.today)
        self.make_subtask(self.today + timedelta(days=1))
        for status in ("done", "pending"):
            data = self.get_today(status=status)
            self.assertEqual(data["para_hoy"]["pospuestas"], [])
            self.assertEqual(data["pospuestas_otros_dias"], 1)

    def test_dias_proximos_zero_means_no_limit(self):
        sub = self.make_subtask(self.today + timedelta(days=30), status="pending")
        self.assertEqual(self.get_today()["proximas"], [])
        data = self.get_today(dias_proximos=0)
        self.assertEqual([s["subtask_id"] for s in data["proximas"]], [sub.pk])
