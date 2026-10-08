from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from event.models import Category, Event, Subtask
from planning.services import daily_load, evaluate_conflict

DAY = date(2026, 10, 5)


class OverloadBase(APITestCase):
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
        self.client.force_authenticate(user=self.user)

    def make_event(self, user, name):
        return Event.objects.create(
            name=name, due_date=timezone.now() + timedelta(days=60), user=user
        )

    def make_subtask(self, hours, day=DAY, event=None, status="pending"):
        return Subtask.objects.create(
            eid=event or self.event,
            title="Tarea",
            category=self.category,
            estimated_hours=Decimal(str(hours)),
            scheduled_date=day,
            status=status,
        )

    def create_payload(self, hours, day=DAY, **extra):
        return {
            "title": "Nueva",
            "category": self.category.name,
            "estimated_hours": hours,
            "scheduled_date": day.isoformat(),
            **extra,
        }

    def post_subtask(self, payload, event=None):
        url = reverse("event:event-subtasks", kwargs={"eid": (event or self.event).pk})
        return self.client.post(url, payload, format="json")


class ConflictServiceTests(OverloadBase):
    def test_no_conflict_at_exact_limit(self):
        self.make_subtask(5)
        result = evaluate_conflict(self.user, DAY, Decimal("1"))
        self.assertFalse(result["has_conflict"])
        self.assertEqual(result["projected"], Decimal("6"))
        self.assertEqual(result["excess"], Decimal("0"))

    def test_conflict_over_limit(self):
        self.make_subtask(5)
        result = evaluate_conflict(self.user, DAY, Decimal("1.5"))
        self.assertTrue(result["has_conflict"])
        self.assertEqual(result["excess"], Decimal("0.5"))

    def test_organizer_limit_is_used(self):
        self.user.max_daily_hours = Decimal("4")
        self.make_subtask(3)
        self.assertTrue(evaluate_conflict(self.user, DAY, Decimal("2"))["has_conflict"])

    def test_postponed_does_not_count_and_done_does(self):
        self.make_subtask(3, status="postponed")
        self.make_subtask(2, status="done")
        self.assertEqual(daily_load(self.user, DAY), Decimal("2"))

    def test_other_organizer_does_not_count(self):
        self.make_subtask(5, event=self.make_event(self.other, "B"))
        self.assertEqual(daily_load(self.user, DAY), Decimal("0"))

    def test_load_spans_all_events(self):
        self.make_subtask(3)
        self.make_subtask(2, event=self.make_event(self.user, "B"))
        self.assertEqual(daily_load(self.user, DAY), Decimal("5"))

    def test_exclude_subtask(self):
        own = self.make_subtask(3)
        self.assertEqual(daily_load(self.user, DAY, exclude_subtask_id=own.pk), Decimal("0"))

    def test_suggested_dates_skip_full_days_and_max_three(self):
        self.make_subtask(6, day=DAY + timedelta(days=1))
        self.make_subtask(5.5, day=DAY + timedelta(days=2))
        result = evaluate_conflict(self.user, DAY, Decimal("1"))
        self.assertEqual(
            result["suggested_dates"],
            [DAY + timedelta(days=d) for d in (3, 4, 5)],
        )

    def test_suggestions_use_single_aggregated_query(self):
        self.make_subtask(5)
        with self.assertNumQueries(2):
            evaluate_conflict(self.user, DAY, Decimal("2"))

    def test_max_hours_none_when_day_is_full(self):
        self.make_subtask(6)
        self.assertIsNone(evaluate_conflict(self.user, DAY, Decimal("1"))["max_hours"])

    def test_max_hours_is_remaining_capacity(self):
        self.make_subtask(5)
        self.assertEqual(evaluate_conflict(self.user, DAY, Decimal("2"))["max_hours"], Decimal("1"))


class CreateConflictTests(OverloadBase):
    def test_create_without_conflict(self):
        self.make_subtask(5)
        response = self.post_subtask(self.create_payload(1))
        self.assertEqual(response.status_code, 201)

    def test_create_with_conflict_returns_409_and_saves_nothing(self):
        self.make_subtask(5)
        response = self.post_subtask(self.create_payload(2))
        self.assertEqual(response.status_code, 409)
        error = response.data["error"]
        self.assertEqual(error["code"], "DAILY_OVERLOAD")
        self.assertEqual(error["message"], "Quedarías con 7h de gestión planificadas (límite 6h)")
        self.assertEqual(
            error["detalle"],
            {"fecha": "2026-10-05", "horas_planificadas": 7.0, "limite": 6.0, "exceso": 1.0},
        )
        self.assertEqual(
            error["alternativas"],
            [
                {"tipo": "mover", "fechas_sugeridas": ["2026-10-06", "2026-10-07", "2026-10-08"]},
                {"tipo": "reducir_horas", "horas_maximas": 1.0},
                {"tipo": "posponer"},
            ],
        )
        self.assertEqual(Subtask.objects.count(), 1)

    def test_message_keeps_decimals(self):
        self.make_subtask(5)
        response = self.post_subtask(self.create_payload(2.5))
        self.assertEqual(
            response.data["error"]["message"],
            "Quedarías con 7.5h de gestión planificadas (límite 6h)",
        )

    def test_create_with_confirm_saves(self):
        self.make_subtask(5)
        response = self.post_subtask(self.create_payload(2, confirm=True))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Subtask.objects.count(), 2)

    def test_confirm_string_true_confirms_and_false_does_not(self):
        self.make_subtask(5)
        self.assertEqual(self.post_subtask(self.create_payload(2, confirm="false")).status_code, 409)
        self.assertEqual(self.post_subtask(self.create_payload(2, confirm="true")).status_code, 201)

    def test_invalid_confirm_is_400(self):
        response = self.post_subtask(self.create_payload(1, confirm="maybe"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm", response.data["error"]["details"])
        self.assertEqual(Subtask.objects.count(), 0)

    def test_validation_error_comes_before_conflict(self):
        self.make_subtask(6)
        response = self.post_subtask(self.create_payload(0))
        self.assertEqual(response.status_code, 400)

    def test_created_as_postponed_is_not_evaluated(self):
        self.make_subtask(6)
        response = self.post_subtask(self.create_payload(3, status="postponed"))
        self.assertEqual(response.status_code, 201)

    def test_full_day_omits_reducir_horas(self):
        self.make_subtask(6)
        response = self.post_subtask(self.create_payload(1))
        types = [a["tipo"] for a in response.data["error"]["alternativas"]]
        self.assertEqual(types, ["mover", "posponer"])


class ReprogramTests(OverloadBase):
    def reprogram(self, subtask, payload):
        url = reverse("event:subtask-reprogram", kwargs={"subtask_id": subtask.pk})
        return self.client.patch(url, payload, format="json")

    def test_reprogram_without_conflict(self):
        subtask = self.make_subtask(2)
        response = self.reprogram(subtask, {"scheduled_date": "2026-10-06"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scheduled_date"], "2026-10-06")
        self.assertEqual(response.data["status"], "pending")
        self.assertFalse(response.data["conflicto"]["hay_conflicto"])
        subtask.refresh_from_db()
        self.assertEqual(subtask.scheduled_date, date(2026, 10, 6))

    def test_scenario_overload_across_events(self):
        self.make_subtask(3)
        self.make_subtask(2, event=self.make_event(self.user, "B"))
        moving = self.make_subtask(2, day=DAY + timedelta(days=3), event=self.make_event(self.user, "C"))
        response = self.reprogram(moving, {"scheduled_date": DAY.isoformat()})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["detalle"]["horas_planificadas"], 7.0)
        self.assertEqual(
            response.data["error"]["message"],
            "Quedarías con 7h de gestión planificadas (límite 6h)",
        )
        moving.refresh_from_db()
        self.assertEqual(moving.scheduled_date, DAY + timedelta(days=3))

    def test_confirm_saves_despite_conflict(self):
        self.make_subtask(5)
        moving = self.make_subtask(2, day=DAY + timedelta(days=1))
        response = self.reprogram(moving, {"scheduled_date": DAY.isoformat(), "confirm": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["conflicto"]["hay_conflicto"])
        moving.refresh_from_db()
        self.assertEqual(moving.scheduled_date, DAY)

    def test_same_day_is_not_double_counted(self):
        subtask = self.make_subtask(5)
        response = self.reprogram(subtask, {"scheduled_date": DAY.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["conflicto"]["horas_planificadas"], 5.0)

    def test_organizer_limit_applies(self):
        self.user.max_daily_hours = Decimal("4")
        self.user.save()
        self.make_subtask(3)
        moving = self.make_subtask(2, day=DAY + timedelta(days=1))
        response = self.reprogram(moving, {"scheduled_date": DAY.isoformat()})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["detalle"]["limite"], 4.0)

    def test_invalid_or_missing_date_is_400(self):
        subtask = self.make_subtask(2)
        for payload in ({}, {"scheduled_date": "not-a-date"}, {"scheduled_date": None}):
            response = self.reprogram(subtask, payload)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.data["success"])
            self.assertIn(
                "La fecha objetivo no es válida.", response.data["error"]["details"]["scheduled_date"]
            )

    def test_past_date_allowed(self):
        subtask = self.make_subtask(2)
        response = self.reprogram(subtask, {"scheduled_date": "2020-01-01"})
        self.assertEqual(response.status_code, 200)

    def test_postponed_does_not_count_on_target_day(self):
        self.make_subtask(6, status="postponed")
        subtask = self.make_subtask(2, day=DAY + timedelta(days=1))
        response = self.reprogram(subtask, {"scheduled_date": DAY.isoformat()})
        self.assertEqual(response.status_code, 200)

    def test_postponed_subtask_moves_without_blocking(self):
        self.make_subtask(6)
        subtask = self.make_subtask(3, day=DAY + timedelta(days=1), status="postponed")
        response = self.reprogram(subtask, {"scheduled_date": DAY.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "postponed")

    def test_done_counts_on_target_day(self):
        self.make_subtask(5, status="done")
        subtask = self.make_subtask(2, day=DAY + timedelta(days=1))
        self.assertEqual(self.reprogram(subtask, {"scheduled_date": DAY.isoformat()}).status_code, 409)

    def test_other_organizer_subtasks_do_not_count_and_are_404(self):
        theirs = self.make_subtask(5, event=self.make_event(self.other, "B"))
        mine = self.make_subtask(2, day=DAY + timedelta(days=1))
        self.assertEqual(self.reprogram(mine, {"scheduled_date": DAY.isoformat()}).status_code, 200)
        self.assertEqual(self.reprogram(theirs, {"scheduled_date": DAY.isoformat()}).status_code, 404)
