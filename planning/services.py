"""Pure functions for daily load/progress, shared across views."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from event.models import Subtask

# Date, then effort, then id as a stable tiebreaker (== urgency_score(weight=0)).
SUBTASK_ORDERING = ("scheduled_date", "estimated_hours", "subtask_id")

# Postponed subtasks moved off this date, so they don't count toward progress.
_PROGRESS_STATUSES = ("pending", "done")


def urgency_score(subtask, event_weight=0):
    """estimated_hours plus a bonus for events closer to their due date (not in the API yet)."""
    weight = Decimal(event_weight)
    if weight == 0:
        return subtask.estimated_hours

    days = (subtask.eid.due_date.date() - subtask.scheduled_date).days
    days = max(days, 0)
    closeness = Decimal(1) / (Decimal(days) + Decimal(1))
    return subtask.estimated_hours + weight * closeness


def group_subtasks(organizer, today, event_id=None, days_ahead=7, status=None):
    """Buckets subtasks into overdue/today/upcoming/postponed for the day summary."""
    base = Subtask.objects.for_organizer(organizer).select_related("eid", "category")
    if event_id is not None:
        base = base.filter(eid_id=event_id)

    upcoming_limit = today + timedelta(days=days_ahead)

    overdue = base.filter(scheduled_date__lt=today, status="pending").order_by(*SUBTASK_ORDERING)
    pending_today = base.filter(scheduled_date=today, status="pending").order_by(*SUBTASK_ORDERING)
    # Anything finished today shows up, even if it was overdue or upcoming.
    done_today = base.filter(status="done").filter(
        Q(scheduled_date=today) | Q(executed_at__date=today)
    ).order_by(*SUBTASK_ORDERING)
    upcoming = base.filter(
        scheduled_date__gt=today, scheduled_date__lte=upcoming_limit, status="pending"
    ).order_by(*SUBTASK_ORDERING)
    postponed = base.none()

    if status == "done":
        overdue = base.none()
        pending_today = base.none()
        upcoming = base.none()
    elif status == "pending":
        done_today = base.none()
    elif status == "postponed":
        # Postponed subtasks moved off their date, so they're empty above by default.
        overdue = base.none()
        pending_today = base.none()
        done_today = base.none()
        upcoming = base.none()
        postponed = base.filter(
            status="postponed", scheduled_date__lte=upcoming_limit
        ).order_by(*SUBTASK_ORDERING)

    return {
        "overdue": overdue,
        "today": {"pending": pending_today, "done": done_today},
        "upcoming": upcoming,
        "postponed": postponed,
    }


def day_progress(organizer, today, event_id=None):
    """Progress bar for today: pending/done subtasks scheduled today."""
    qs = Subtask.objects.for_organizer(organizer).filter(
        scheduled_date=today, status__in=_PROGRESS_STATUSES
    )
    if event_id is not None:
        qs = qs.filter(eid_id=event_id)

    aggregates = qs.aggregate(
        completed=Count("subtask_id", filter=Q(status="done")),
        total=Count("subtask_id"),
        completed_hours=Sum("estimated_hours", filter=Q(status="done")),
        total_hours=Sum("estimated_hours"),
    )

    return {
        "completed": aggregates["completed"] or 0,
        "total": aggregates["total"] or 0,
        "completed_hours": aggregates["completed_hours"] or Decimal("0"),
        "total_hours": aggregates["total_hours"] or Decimal("0"),
    }


def event_progress(event):
    """Progress across all of the event's subtasks, any date (US-10)."""
    aggregates = event.subtasks.aggregate(
        completed=Count("subtask_id", filter=Q(status="done")),
        total=Count("subtask_id"),
    )
    completed = aggregates["completed"] or 0
    total = aggregates["total"] or 0

    percentage = int(round((completed / total) * 100)) if total else 0
    return {"completed": completed, "total": total, "percentage": percentage}
