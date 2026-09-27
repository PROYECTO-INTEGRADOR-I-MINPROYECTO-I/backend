"""Comando de datos de demostración.

Crea (o recrea con --reset) un organizador demo con un par de eventos y un
puñado de gestiones en distintos estados, pensado para mostrar /api/today/
sin tener que cargar datos a mano.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from event.models import Category, EventType, Events, Subtasks, Users

DEMO_EMAIL = "demo@planificapp.com"
DEMO_NAME = "Demo"
DEMO_PASSWORD = "demo1234"


class Command(BaseCommand):
    help = "Crea el organizador demo@planificapp.com y datos de demostración."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los eventos demo existentes (y sus gestiones, en cascada) y los recrea.",
        )
        parser.add_argument(
            "--password",
            help=(
                "Contraseña del organizador demo. Si el usuario ya existe solo "
                "se cambia cuando se pasa esta opción (al crearlo: demo1234)."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite correr el comando en prod.",
        )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "prod" and not options["force"]:
            raise CommandError("seed_demo no corre en prod sin --force.")

        reset = options["reset"]
        password = options["password"]

        user, creado = Users.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={
                "name": DEMO_NAME,
                "password_hash": make_password(password or DEMO_PASSWORD),
                "max_daily_hours": Decimal("6.00"),
            },
        )
        if creado:
            password = password or DEMO_PASSWORD
        else:
            # Un usuario demo existente conserva su contraseña y su límite,
            # salvo que se pida explícitamente.
            if password:
                user.password_hash = make_password(password)
            if reset:
                user.max_daily_hours = Decimal("6.00")
            user.save()

        eventos_existentes = Events.objects.filter(user=user)
        if reset:
            eventos_existentes.delete()  # cascada: se llevan también sus gestiones
        elif eventos_existentes.exists():
            self.stdout.write(self.style.WARNING(
                "Ya existen eventos demo para este usuario; no se duplican. "
                "Usa --reset para recrearlos desde cero."
            ))
            self._imprimir_resumen(user, password)
            return

        with transaction.atomic():
            self._crear_datos(user)

        self.stdout.write(self.style.SUCCESS("Datos de demostración creados."))
        self._imprimir_resumen(user, password)

    def _crear_datos(self, user):
        hoy = timezone.localdate()
        categorias = {c.name: c for c in Category.objects.filter(user__isnull=True)}
        tipo_boda = EventType.objects.filter(name="Boda", user__isnull=True).first()

        ev1 = Events.objects.create(
            user=user,
            name="Boda Camila & Esteban",
            description="Organización integral de la boda.",
            due_date=self._a_datetime(hoy + datetime.timedelta(days=30)),
            event_type=tipo_boda,
            place="Hacienda El Roble",
            client_contact="Camila Restrepo - 300 555 1234",
        )
        ev2 = Events.objects.create(
            user=user,
            name="Lanzamiento de producto Nova",
            description="Evento corporativo de lanzamiento.",
            due_date=self._a_datetime(hoy + datetime.timedelta(days=20)),
            place="Centro de Convenciones",
            client_contact="Nova S.A.S. - contacto@nova.com",
        )

        # (evento, categoría, título, fecha, horas, estado)
        gestiones = [
            # Vencidas: dos fechas distintas, ya pasadas.
            (ev1, "Lugar", "Reservar salón", hoy - datetime.timedelta(days=5), "2", "pending"),
            (ev2, "Marketing", "Publicar flyer de lanzamiento", hoy - datetime.timedelta(days=2), "1.5", "pending"),
            # Hoy: dos pendientes con distinto esfuerzo + una ya ejecutada.
            (ev1, "Catering", "Cotizar catering", hoy, "2", "pending"),
            (ev2, "Logística técnica", "Confirmar equipo de sonido", hoy, "3", "pending"),
            (ev1, "Invitaciones", "Enviar invitaciones digitales", hoy, "1", "done"),
            # Próximas: incluyen dos gestiones con la misma fecha y distinto esfuerzo.
            (ev1, "Proveedores", "Contratar decorador", hoy + datetime.timedelta(days=3), "2", "pending"),
            (ev2, "Personal/Conferencistas", "Confirmar conferencista invitado", hoy + datetime.timedelta(days=3), "4", "pending"),
            (ev2, "Marketing", "Diseñar piezas para redes sociales", hoy + datetime.timedelta(days=5), "1", "pending"),
            # hoy+2 queda cargado a exactamente 6h entre los dos eventos: sumar
            # 1h más ahí dispara el conflicto de límite diario (6h + 1h = 7h).
            (ev1, "Lugar", "Coordinar montaje del lugar", hoy + datetime.timedelta(days=2), "4", "pending"),
            (ev2, "Logística técnica", "Alquilar equipo audiovisual", hoy + datetime.timedelta(days=2), "2", "pending"),
        ]

        for evento, categoria, titulo, fecha, horas, status in gestiones:
            subtask = Subtasks.objects.create(
                eid=evento,
                title=titulo,
                category=categorias[categoria],
                estimated_hours=Decimal(horas),
                scheduled_date=fecha,
                status=status,
            )
            if status == "done":
                subtask.executed_at = timezone.now()
                subtask.save(update_fields=["executed_at"])

    @staticmethod
    def _a_datetime(fecha):
        return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(hour=10)))

    def _imprimir_resumen(self, user, password):
        eventos = Events.objects.filter(user=user)
        total_gestiones = Subtasks.objects.del_organizador(user).count()

        self.stdout.write("")
        self.stdout.write("Credenciales del organizador demo:")
        self.stdout.write(f"  email:    {user.email}")
        self.stdout.write(f"  password: {password or '(sin cambios)'}")
        self.stdout.write("")
        self.stdout.write(f"Eventos: {eventos.count()} | Gestiones: {total_gestiones}")
        for evento in eventos:
            self.stdout.write(f"  - {evento.name} (eid={evento.eid})")
