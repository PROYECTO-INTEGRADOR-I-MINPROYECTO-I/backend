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


# Statuses that consume daily capacity; postponed ones don't.
_LOAD_STATUSES = ("pending", "done")
SUGGESTION_LOOKAHEAD_DAYS = 30
MAX_SUGGESTED_DATES = 3


def _to_decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _load_qs(organizer, exclude_subtask_id=None):
    qs = Subtask.objects.for_organizer(organizer).filter(status__in=_LOAD_STATUSES)
    if exclude_subtask_id is not None:
        qs = qs.exclude(subtask_id=exclude_subtask_id)
    return qs


def daily_load(organizer, day, exclude_subtask_id=None):
    """Hours planned (pending + done) across all the organizer's events on a day."""
    total = _load_qs(organizer, exclude_subtask_id).filter(scheduled_date=day).aggregate(
        total=Sum("estimated_hours")
    )["total"]
    return total or Decimal("0")


def days_over_limit(organizer, limit, since):
    """Days from `since` on whose planned hours exceed `limit`, as (date, hours) pairs."""
    rows = (
        _load_qs(organizer)
        .filter(scheduled_date__gte=since)
        .values("scheduled_date")
        .annotate(total=Sum("estimated_hours"))
        .filter(total__gt=limit)
        .order_by("scheduled_date")
    )
    return [(row["scheduled_date"], row["total"]) for row in rows]


def evaluate_conflict(organizer, day, hours, exclude_subtask_id=None):
    """Checks whether adding `hours` to `day` goes over the organizer's daily limit."""
    limit = _to_decimal(organizer.max_daily_hours)
    hours = _to_decimal(hours)
    load = daily_load(organizer, day, exclude_subtask_id)
    projected = load + hours
    excess = max(projected - limit, Decimal("0"))

    window_end = day + timedelta(days=SUGGESTION_LOOKAHEAD_DAYS)
    rows = (
        _load_qs(organizer, exclude_subtask_id)
        .filter(scheduled_date__gt=day, scheduled_date__lte=window_end)
        .values("scheduled_date")
        .annotate(total=Sum("estimated_hours"))
    )
    loads = {row["scheduled_date"]: row["total"] for row in rows}

    suggested_dates = []
    for offset in range(1, SUGGESTION_LOOKAHEAD_DAYS + 1):
        candidate = day + timedelta(days=offset)
        if limit - loads.get(candidate, Decimal("0")) >= hours:
            suggested_dates.append(candidate)
            if len(suggested_dates) == MAX_SUGGESTED_DATES:
                break

    max_hours = limit - load
    return {
        "has_conflict": projected > limit,
        "date": day,
        "projected": projected,
        "limit": limit,
        "excess": excess,
        "suggested_dates": suggested_dates,
        "max_hours": max_hours if max_hours > 0 else None,
    }
