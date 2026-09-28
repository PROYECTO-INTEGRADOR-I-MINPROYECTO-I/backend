from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from accounts.models import User


class EventType(models.Model):
    event_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    # user = None -> predefined type, available to every organizer.
    user = models.ForeignKey(
        User, models.CASCADE, null=True, blank=True, related_name='event_types'
    )

    class Meta:
        db_table = 'event_types'
        constraints = [
            models.UniqueConstraint(Lower('name'), 'user', name='unique_event_type_name_per_user'),
            models.UniqueConstraint(
                Lower('name'),
                condition=Q(user__isnull=True),
                name='unique_predefined_event_type_name',
            ),
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    # user = None -> predefined category, available to every organizer.
    user = models.ForeignKey(
        User, models.CASCADE, null=True, blank=True, related_name='categories'
    )

    class Meta:
        db_table = 'categories'
        constraints = [
            models.UniqueConstraint(Lower('name'), 'user', name='unique_category_name_per_user'),
            models.UniqueConstraint(
                Lower('name'),
                condition=Q(user__isnull=True),
                name='unique_predefined_category_name',
            ),
        ]

    def __str__(self):
        return self.name


class Event(models.Model):
    eid = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, models.CASCADE)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField()
    event_type = models.ForeignKey(
        EventType, models.SET_NULL, null=True, blank=True, related_name='events'
    )
    place = models.CharField(max_length=255, blank=True, null=True)
    client_contact = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'events'
        indexes = [
            models.Index(fields=['user'], name='events_user_idx'),
            models.Index(fields=['due_date'], name='events_due_date_idx'),
        ]

    def __str__(self):
        return self.name


class SubtaskQuerySet(models.QuerySet):
    def for_organizer(self, user):
        # No direct FK to User; owner comes from the parent event.
        return self.filter(eid__user=user)


class Subtask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'pending'),
        ('done', 'done'),
        ('postponed', 'postponed'),
    ]

    objects = SubtaskQuerySet.as_manager()

    subtask_id = models.AutoField(primary_key=True)
    eid = models.ForeignKey('Event', models.CASCADE, db_column='eid', related_name='subtasks')
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, models.PROTECT, related_name='subtasks')
    estimated_hours = models.DecimalField(max_digits=4, decimal_places=2)
    scheduled_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    postpone_note = models.TextField(blank=True, null=True)
    executed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subtasks'
        indexes = [
            models.Index(fields=['eid'], name='subtasks_eid_idx'),
            models.Index(fields=['scheduled_date'], name='subtasks_scheduled_date_idx'),
        ]

    def __str__(self):
        return self.title
