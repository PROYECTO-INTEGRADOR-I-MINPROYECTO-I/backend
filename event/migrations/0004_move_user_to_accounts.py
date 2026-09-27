import django.db.models.deletion
from django.db import migrations, models

# Content types keyed by the old (app_label, model) pairs. Django only renames
# them automatically for top-level RenameModel operations, and ours live inside
# SeparateDatabaseAndState, so we move them by hand to keep their permissions.
RENAMED_CONTENT_TYPES = [
    (("event", "users"), ("accounts", "user")),
    (("event", "events"), ("event", "event")),
    (("event", "subtasks"), ("event", "subtask")),
]


def _move_content_types(apps, pairs):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for (old_app, old_model), (new_app, new_model) in pairs:
        old = ContentType.objects.filter(app_label=old_app, model=old_model).first()
        if old is None:
            continue
        if ContentType.objects.filter(app_label=new_app, model=new_model).exists():
            # The new one was already created (e.g. by post_migrate); drop the stale row.
            old.delete()
        else:
            old.app_label, old.model = new_app, new_model
            old.save(update_fields=["app_label", "model"])


def forwards_content_types(apps, schema_editor):
    _move_content_types(apps, RENAMED_CONTENT_TYPES)


def backwards_content_types(apps, schema_editor):
    _move_content_types(apps, [(new, old) for old, new in RENAMED_CONTENT_TYPES])


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0003_subtask_category_requerida'),
        ('accounts', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
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
        migrations.RunPython(forwards_content_types, backwards_content_types),
    ]
