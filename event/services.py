"""Servicio de agregación de carga diaria y progreso.

Funciones puras (sin request/response): reciben organizador/objetos y
devuelven datos o querysets. Así se pueden reusar desde vistas distintas
(creación/edición de subtareas, endpoint de "hoy", etc.) sin duplicar la
regla de negocio.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from .models import Subtasks

# DECISIÓN DEL EQUIPO: la carga diaria de un día cuenta las gestiones
# pendientes y las ya ejecutadas (el tiempo que tomó "done" ya ocupó la
# disponibilidad de ese día), y excluye las pospuestas (se movieron a otra
# fecha, no ocupan el día original). Este es el único lugar donde vive esta
# regla; cualquier cálculo de carga debe pasar por carga_diaria/evaluar_conflicto.
ESTADOS_CARGA = ("pending", "done")

# Orden usado para listar gestiones: por fecha, luego por esfuerzo y por id
# como desempate estable. Equivale a puntaje_urgencia con peso_evento=0.
ORDEN_GESTIONES = ("scheduled_date", "estimated_hours", "subtask_id")


def _formatear_horas(valor):
    # Evita ceros sobrantes en los mensajes (7.00 -> "7", 6.50 -> "6.5") sin
    # caer en notación científica al normalizar Decimals redondos.
    return format(valor.normalize(), "f")


def carga_diaria(organizador, fecha, excluir_subtask_id=None):
    """Suma de horas estimadas de las gestiones que cuentan para la carga
    del organizador en `fecha` (ver ESTADOS_CARGA)."""
    qs = Subtasks.objects.del_organizador(organizador).filter(
        scheduled_date=fecha, status__in=ESTADOS_CARGA
    )
    if excluir_subtask_id is not None:
        qs = qs.exclude(pk=excluir_subtask_id)

    total = qs.aggregate(total=Sum("estimated_hours"))["total"]
    return total if total is not None else Decimal("0")


def evaluar_conflicto(organizador, fecha, horas_nuevas, excluir_subtask_id=None):
    """Evalúa si sumar `horas_nuevas` ese día superaría el límite diario del
    organizador. No bloquea nada: solo informa (el bloqueo es de otra historia)."""
    limite = organizador.max_daily_hours
    carga = carga_diaria(organizador, fecha, excluir_subtask_id=excluir_subtask_id)
    total = carga + horas_nuevas
    hay_conflicto = total > limite

    mensaje = None
    if hay_conflicto:
        mensaje = (
            f"Quedarías con {_formatear_horas(total)}h de gestión planificadas "
            f"(límite {_formatear_horas(limite)}h)"
        )

    return {
        "hay_conflicto": hay_conflicto,
        "horas_planificadas": total,
        "limite": limite,
        "fecha": fecha,
        "mensaje": mensaje,
    }


def puntaje_urgencia(subtask, peso_evento=0):
    """Combina estimated_hours con la cercanía de la fecha límite del
    evento (días entre scheduled_date y eid.due_date).

    peso_evento es un parámetro interno, no expuesto en la API: con 0 el
    puntaje es simplemente estimated_hours (el orden equivalente en BD es
    ORDEN_GESTIONES); un peso mayor prioriza gestiones de eventos más
    próximos a vencer.
    """
    peso = Decimal(peso_evento)
    if peso == 0:
        return subtask.estimated_hours

    dias = (subtask.eid.due_date.date() - subtask.scheduled_date).days
    dias = max(dias, 0)
    cercania = Decimal(1) / (Decimal(dias) + Decimal(1))
    return subtask.estimated_hours + peso * cercania


def agrupar_gestiones(organizador, hoy, evento_id=None, dias_proximos=7, estado=None):
    """Arma las listas de gestiones para el resumen del día.

    - vencidas: fecha < hoy y pending.
    - para_hoy: pendientes y completadas de hoy, separadas.
    - proximas: entre hoy (exclusive) y hoy + dias_proximos, pending.
    - Las gestiones 'postponed' NO aparecen en ninguna de las listas de
      arriba (se movieron a otra fecha); solo se listan en "pospuestas",
      clave que devolvemos siempre pero que solo se llena cuando
      estado == "postponed" (si no, viene vacía).
    - `estado` (uno de los valores del modelo, o None) filtra qué listas
      traen datos y cuáles quedan vacías (.none()): pending y done ya están
      separados por lista, así que filtrar por uno de esos dos solo vacía
      la lista contraria (pendientes/completadas); postponed vacía todas
      las listas normales y llena "pospuestas".
    """
    base = Subtasks.objects.del_organizador(organizador).select_related("eid", "category")
    if evento_id is not None:
        base = base.filter(eid_id=evento_id)

    limite_proximas = hoy + timedelta(days=dias_proximos)

    vencidas = base.filter(scheduled_date__lt=hoy, status="pending").order_by(*ORDEN_GESTIONES)
    pendientes_hoy = base.filter(scheduled_date=hoy, status="pending").order_by(*ORDEN_GESTIONES)
    completadas_hoy = base.filter(scheduled_date=hoy, status="done").order_by(*ORDEN_GESTIONES)
    proximas = base.filter(
        scheduled_date__gt=hoy, scheduled_date__lte=limite_proximas, status="pending"
    ).order_by(*ORDEN_GESTIONES)
    pospuestas = base.none()

    if estado == "done":
        vencidas = base.none()
        pendientes_hoy = base.none()
        proximas = base.none()
    elif estado == "pending":
        completadas_hoy = base.none()
    elif estado == "postponed":
        vencidas = base.none()
        pendientes_hoy = base.none()
        completadas_hoy = base.none()
        proximas = base.none()
        pospuestas = base.filter(
            status="postponed", scheduled_date__lte=limite_proximas
        ).order_by(*ORDEN_GESTIONES)

    return {
        "vencidas": vencidas,
        "para_hoy": {"pendientes": pendientes_hoy, "completadas": completadas_hoy},
        "proximas": proximas,
        "pospuestas": pospuestas,
    }


def progreso_dia(organizador, hoy, evento_id=None):
    """Barra de progreso del día: gestiones de hoy con status pending/done
    (misma partición que para_hoy en agrupar_gestiones). Nunca divide acá;
    total en 0 si no hay gestiones ese día."""
    qs = Subtasks.objects.del_organizador(organizador).filter(
        scheduled_date=hoy, status__in=ESTADOS_CARGA
    )
    if evento_id is not None:
        qs = qs.filter(eid_id=evento_id)

    agregados = qs.aggregate(
        completadas=Count("subtask_id", filter=Q(status="done")),
        total=Count("subtask_id"),
        horas_completadas=Sum("estimated_hours", filter=Q(status="done")),
        horas_totales=Sum("estimated_hours"),
    )

    return {
        "completadas": agregados["completadas"] or 0,
        "total": agregados["total"] or 0,
        "horas_completadas": agregados["horas_completadas"] or Decimal("0"),
        "horas_totales": agregados["horas_totales"] or Decimal("0"),
    }


def anotar_progreso(queryset):
    """Anota completadas/total por evento en el propio queryset, para que
    progreso_evento no dispare una consulta extra por cada evento listado
    (evita N+1 en EventListCreateView)."""
    return queryset.annotate(
        _completadas_anotadas=Count("subtasks", filter=Q(subtasks__status="done")),
        _total_anotado=Count("subtasks"),
    )


def progreso_evento(evento):
    """Progreso de TODAS las gestiones del evento (done/total), sin
    importar la fecha. Usa las anotaciones de anotar_progreso si ya vienen
    en el objeto; si no, agrega en BD sobre evento.subtasks."""
    completadas = getattr(evento, "_completadas_anotadas", None)
    total = getattr(evento, "_total_anotado", None)

    if completadas is None or total is None:
        agregados = evento.subtasks.aggregate(
            completadas=Count("subtask_id", filter=Q(status="done")),
            total=Count("subtask_id"),
        )
        completadas = agregados["completadas"] or 0
        total = agregados["total"] or 0

    porcentaje = int(round((completadas / total) * 100)) if total else 0
    return {"completadas": completadas, "total": total, "porcentaje": porcentaje}
