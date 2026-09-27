"""Daily load and progress aggregation service.

Pure functions (no request/response): they receive an organizer/objects and
return data or querysets. This way they can be reused from different views
(subtask creation/edit, the "today" endpoint, etc.) without duplicating the
business rule.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from event.models import Subtask

# TEAM DECISION: a day's load counts pending and already done subtasks (the
# time a "done" subtask took already occupied that day's availability), and
# excludes postponed ones (they moved to another date, they don't occupy the
# original day). This is the only place this rule lives; any load
# calculation must go through daily_load/evaluate_overload.
LOAD_STATUSES = ("pending", "done")

# Ordering used to list subtasks: by date, then by effort and id as a stable
# tiebreaker. Equivalent to urgency_score with event_weight=0.
SUBTASK_ORDERING = ("scheduled_date", "estimated_hours", "subtask_id")


def _format_hours(value):
    # Avoids trailing zeros in messages (7.00 -> "7", 6.50 -> "6.5") without
    # falling into scientific notation when normalizing round Decimals.
    return format(value.normalize(), "f")


def daily_load(organizer, date, exclude_subtask_id=None):
    """Sum of estimated hours of the subtasks that count toward the
    organizer's load on `date` (see LOAD_STATUSES)."""
    qs = Subtask.objects.for_organizer(organizer).filter(
        scheduled_date=date, status__in=LOAD_STATUSES
    )
    if exclude_subtask_id is not None:
        qs = qs.exclude(pk=exclude_subtask_id)

    total = qs.aggregate(total=Sum("estimated_hours"))["total"]
    return total if total is not None else Decimal("0")


def evaluate_overload(organizer, date, new_hours, exclude_subtask_id=None):
    """Evaluates whether adding `new_hours` that day would exceed the
    organizer's daily limit. Doesn't block anything: it just informs (the
    block, if any, belongs to another story)."""
    limit = organizer.max_daily_hours
    load = daily_load(organizer, date, exclude_subtask_id=exclude_subtask_id)
    total = load + new_hours
    has_conflict = total > limit

    message = None
    if has_conflict:
        message = (
            f"Quedarías con {_format_hours(total)}h de gestión planificadas "
            f"(límite {_format_hours(limit)}h)"
        )

    return {
        "has_conflict": has_conflict,
        "planned_hours": total,
        "limit": limit,
        "date": date,
        "message": message,
    }


def urgency_score(subtask, event_weight=0):
    """Combines estimated_hours with how close the event's due date is
    (days between scheduled_date and eid.due_date).

    event_weight is an internal parameter, not exposed in the API: with 0
    the score is simply estimated_hours (the equivalent DB ordering is
    SUBTASK_ORDERING); a higher weight prioritizes subtasks of events closer
    to their deadline.
    """
    weight = Decimal(event_weight)
    if weight == 0:
        return subtask.estimated_hours

    days = (subtask.eid.due_date.date() - subtask.scheduled_date).days
    days = max(days, 0)
    closeness = Decimal(1) / (Decimal(days) + Decimal(1))
    return subtask.estimated_hours + weight * closeness


def group_subtasks(organizer, today, event_id=None, days_ahead=7, status=None):
    """Builds the subtask lists for the day summary.

    - overdue: date < today and pending.
    - today: pending and done subtasks of today, kept separate.
    - upcoming: between today (exclusive) and today + days_ahead, pending.
    - Postponed subtasks do NOT appear in any of the lists above (they moved
      to another date); they only show up in "postponed", a key that's
      always returned but only filled in when status == "postponed" (empty
      otherwise).
    - `status` (one of the model's values, or None) filters which lists
      carry data and which come back empty (.none()): pending and done are
      already split by list, so filtering by one of those two only empties
      the opposite list (pending/done); postponed empties all the normal
      lists and fills "postponed".
    """
    base = Subtask.objects.for_organizer(organizer).select_related("eid", "category")
    if event_id is not None:
        base = base.filter(eid_id=event_id)

    upcoming_limit = today + timedelta(days=days_ahead)

    overdue = base.filter(scheduled_date__lt=today, status="pending").order_by(*SUBTASK_ORDERING)
    pending_today = base.filter(scheduled_date=today, status="pending").order_by(*SUBTASK_ORDERING)
    done_today = base.filter(scheduled_date=today, status="done").order_by(*SUBTASK_ORDERING)
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
    """Today's progress bar: today's subtasks with status pending/done (same
    split as "today" in group_subtasks). Never divides here; total is 0 if
    there are no subtasks that day."""
    qs = Subtask.objects.for_organizer(organizer).filter(
        scheduled_date=today, status__in=LOAD_STATUSES
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


def annotate_progress(queryset):
    """Annotates completed/total per event on the queryset itself, so
    event_progress doesn't fire an extra query per listed event (avoids N+1
    in EventListCreateView)."""
    return queryset.annotate(
        _annotated_completed=Count("subtasks", filter=Q(subtasks__status="done")),
        _annotated_total=Count("subtasks"),
    )


def event_progress(event):
    """Progress of ALL of the event's subtasks (done/total), regardless of
    date. Uses annotate_progress's annotations if already present on the
    object; otherwise aggregates in DB over event.subtasks."""
    completed = getattr(event, "_annotated_completed", None)
    total = getattr(event, "_annotated_total", None)

    if completed is None or total is None:
        aggregates = event.subtasks.aggregate(
            completed=Count("subtask_id", filter=Q(status="done")),
            total=Count("subtask_id"),
        )
        completed = aggregates["completed"] or 0
        total = aggregates["total"] or 0

    percentage = int(round((completed / total) * 100)) if total else 0
    return {"completed": completed, "total": total, "percentage": percentage}
