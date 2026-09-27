"""Demo data command.

Creates (or recreates with --reset) a demo organizer with a couple of
events and a handful of subtasks in different states, meant to show
/api/today/ without loading data by hand.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from event.models import Category, Event, EventType, Subtask

DEMO_EMAIL = "demo@planificapp.com"
DEMO_NAME = "Demo"
DEMO_PASSWORD = "demo1234"


class Command(BaseCommand):
    help = "Creates the demo@planificapp.com organizer and demo data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Deletes the existing demo events (and their subtasks, cascading) and recreates them.",
        )
        parser.add_argument(
            "--password",
            help=(
                "Password for the demo organizer. If the user already exists it's only "
                "changed when this option is passed (on creation: demo1234)."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allows running the command in prod.",
        )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "prod" and not options["force"]:
            raise CommandError("seed_demo doesn't run in prod without --force.")

        reset = options["reset"]
        password = options["password"]

        user, created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={
                "name": DEMO_NAME,
                "password_hash": make_password(password or DEMO_PASSWORD),
                "max_daily_hours": Decimal("6.00"),
            },
        )
        if created:
            password = password or DEMO_PASSWORD
        else:
            # An existing demo user keeps its password and its limit, unless
            # explicitly asked to change them.
            if password:
                user.password_hash = make_password(password)
            if reset:
                user.max_daily_hours = Decimal("6.00")
            user.save()

        existing_events = Event.objects.filter(user=user)
        if reset:
            existing_events.delete()  # cascades: their subtasks go with them
        elif existing_events.exists():
            self.stdout.write(self.style.WARNING(
                "Demo events already exist for this user; they won't be duplicated. "
                "Use --reset to recreate them from scratch."
            ))
            self._print_summary(user, password)
            return

        with transaction.atomic():
            self._create_data(user)

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self._print_summary(user, password)

    def _create_data(self, user):
        today = timezone.localdate()
        categories = {c.name: c for c in Category.objects.filter(user__isnull=True)}
        wedding_type = EventType.objects.filter(name="Boda", user__isnull=True).first()

        ev1 = Event.objects.create(
            user=user,
            name="Boda Camila & Esteban",
            description="Organización integral de la boda.",
            due_date=self._to_datetime(today + datetime.timedelta(days=30)),
            event_type=wedding_type,
            place="Hacienda El Roble",
            client_contact="Camila Restrepo - 300 555 1234",
        )
        ev2 = Event.objects.create(
            user=user,
            name="Lanzamiento de producto Nova",
            description="Evento corporativo de lanzamiento.",
            due_date=self._to_datetime(today + datetime.timedelta(days=20)),
            place="Centro de Convenciones",
            client_contact="Nova S.A.S. - contacto@nova.com",
        )

        # (event, category, title, date, hours, status)
        subtasks = [
            # Overdue: two different dates, already past.
            (ev1, "Lugar", "Reservar salón", today - datetime.timedelta(days=5), "2", "pending"),
            (ev2, "Marketing", "Publicar flyer de lanzamiento", today - datetime.timedelta(days=2), "1.5", "pending"),
            # Today: two pending with different effort + one already done.
            (ev1, "Catering", "Cotizar catering", today, "2", "pending"),
            (ev2, "Logística técnica", "Confirmar equipo de sonido", today, "3", "pending"),
            (ev1, "Invitaciones", "Enviar invitaciones digitales", today, "1", "done"),
            # Upcoming: includes two subtasks on the same date with different effort.
            (ev1, "Proveedores", "Contratar decorador", today + datetime.timedelta(days=3), "2", "pending"),
            (ev2, "Personal/Conferencistas", "Confirmar conferencista invitado", today + datetime.timedelta(days=3), "4", "pending"),
            (ev2, "Marketing", "Diseñar piezas para redes sociales", today + datetime.timedelta(days=5), "1", "pending"),
            # today+2 ends up loaded to exactly 6h between both events: adding
            # 1h more there triggers the daily limit conflict (6h + 1h = 7h).
            (ev1, "Lugar", "Coordinar montaje del lugar", today + datetime.timedelta(days=2), "4", "pending"),
            (ev2, "Logística técnica", "Alquilar equipo audiovisual", today + datetime.timedelta(days=2), "2", "pending"),
        ]

        for event, category, title, date, hours, status in subtasks:
            subtask = Subtask.objects.create(
                eid=event,
                title=title,
                category=categories[category],
                estimated_hours=Decimal(hours),
                scheduled_date=date,
                status=status,
            )
            if status == "done":
                subtask.executed_at = timezone.now()
                subtask.save(update_fields=["executed_at"])

    @staticmethod
    def _to_datetime(date):
        return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hour=10)))

    def _print_summary(self, user, password):
        events = Event.objects.filter(user=user)
        total_subtasks = Subtask.objects.for_organizer(user).count()

        self.stdout.write("")
        self.stdout.write("Demo organizer credentials:")
        self.stdout.write(f"  email:    {user.email}")
        self.stdout.write(f"  password: {password or '(unchanged)'}")
        self.stdout.write("")
        self.stdout.write(f"Events: {events.count()} | Subtasks: {total_subtasks}")
        for event in events:
            self.stdout.write(f"  - {event.name} (eid={event.eid})")
