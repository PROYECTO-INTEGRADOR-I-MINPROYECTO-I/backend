import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0003_subtask_category_requerida'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='events',
                    name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.user'),
                ),
                migrations.AlterField(
                    model_name='eventtype',
                    name='user',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='event_types', to='accounts.user'),
                ),
                migrations.AlterField(
                    model_name='category',
                    name='user',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='categories', to='accounts.user'),
                ),
                migrations.DeleteModel(
                    name='Users',
                ),
                migrations.RenameModel(
                    old_name='Events',
                    new_name='Event',
                ),
                migrations.RenameModel(
                    old_name='Subtasks',
                    new_name='Subtask',
                ),
            ],
        ),
    ]
