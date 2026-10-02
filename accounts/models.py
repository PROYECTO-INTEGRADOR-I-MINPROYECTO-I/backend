from django.db import models


class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.CharField(unique=True, max_length=150)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    max_daily_hours = models.DecimalField(
        max_digits=4, decimal_places=2, default=6.00
    )

    # Bumped on logout: tokens carrying an older "ver" claim stop working.
    token_version = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'users'
