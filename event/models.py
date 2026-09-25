from django.db import models


class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    max_daily_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=6.00
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user"

    def __str__(self):
        return self.name