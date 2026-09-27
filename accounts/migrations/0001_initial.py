from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('event', '0003_subtask_category_requerida'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='User',
                    fields=[
                        ('user_id', models.AutoField(primary_key=True, serialize=False)),
                        ('name', models.CharField(max_length=100)),
                        ('email', models.CharField(max_length=150, unique=True)),
                        ('password_hash', models.CharField(max_length=255)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('max_daily_hours', models.DecimalField(decimal_places=2, default=6.0, max_digits=4)),
                    ],
                    options={
                        'db_table': 'users',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
