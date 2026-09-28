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

# Ordering used to list subtasks: by date, then by effort and id as a stable
# tiebreaker. Equivalent to urgency_score with event_weight=0.
SUBTASK_ORDERING = ("scheduled_date", "estimated_hours", "subtask_id")

# Statuses that count toward a day's progress (pending and already done
# subtasks); postponed ones moved to another date and don't count here.
_PROGRESS_STATUSES = ("pending", "done")


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
    """Progress of ALL of the event's subtasks (done/total), regardless of
    date. Exposed later by US-10."""
    aggregates = event.subtasks.aggregate(
        completed=Count("subtask_id", filter=Q(status="done")),
        total=Count("subtask_id"),
    )
    completed = aggregates["completed"] or 0
    total = aggregates["total"] or 0

    percentage = int(round((completed / total) * 100)) if total else 0
    return {"completed": completed, "total": total, "percentage": percentage}
