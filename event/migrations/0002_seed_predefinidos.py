from django.db import migrations

EVENT_TYPES = ["Boda", "Social", "Corporativo", "Cumpleaños", "Otro"]

CATEGORIES = [
    "Lugar",
    "Catering",
    "Invitaciones",
    "Proveedores",
    "Logística técnica",
    "Personal/Conferencistas",
    "Marketing",
]


def seed_predefinidos(apps, schema_editor):
    EventType = apps.get_model('event', 'EventType')
    Category = apps.get_model('event', 'Category')

    for name in EVENT_TYPES:
        EventType.objects.get_or_create(name=name, user=None)

    for name in CATEGORIES:
        Category.objects.get_or_create(name=name, user=None)


def remove_predefinidos(apps, schema_editor):
    EventType = apps.get_model('event', 'EventType')
    Category = apps.get_model('event', 'Category')

    EventType.objects.filter(name__in=EVENT_TYPES, user__isnull=True).delete()
    Category.objects.filter(name__in=CATEGORIES, user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_predefinidos, remove_predefinidos),
    ]
