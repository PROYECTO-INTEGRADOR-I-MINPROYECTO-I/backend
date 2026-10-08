"""Maps planning conflict evaluations to the Spanish JSON the frontend consumes."""
from rest_framework import status
from rest_framework.response import Response


def _num(value):
    return float(value)


def _fmt(value):
    # 7 -> "7", 7.5 -> "7.5"
    text = format(float(value), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def conflict_summary(evaluation):
    """Small summary attached to 200 responses."""
    return {
        "hay_conflicto": evaluation["has_conflict"],
        "fecha": evaluation["date"].isoformat(),
        "horas_planificadas": _num(evaluation["projected"]),
        "limite": _num(evaluation["limit"]),
        "exceso": _num(evaluation["excess"]),
    }


def overload_payload(evaluation):
    alternatives = []
    if evaluation["suggested_dates"]:
        alternatives.append(
            {
                "tipo": "mover",
                "fechas_sugeridas": [d.isoformat() for d in evaluation["suggested_dates"]],
            }
        )
    if evaluation["max_hours"] is not None:
        alternatives.append(
            {"tipo": "reducir_horas", "horas_maximas": _num(evaluation["max_hours"])}
        )
    alternatives.append({"tipo": "posponer"})

    return {
        "error": {
            "code": "DAILY_OVERLOAD",
            "message": (
                f"Quedarías con {_fmt(evaluation['projected'])}h de gestión "
                f"planificadas (límite {_fmt(evaluation['limit'])}h)"
            ),
            "detalle": {
                "fecha": evaluation["date"].isoformat(),
                "horas_planificadas": _num(evaluation["projected"]),
                "limite": _num(evaluation["limit"]),
                "exceso": _num(evaluation["excess"]),
            },
            "alternativas": alternatives,
        }
    }


def overload_response(evaluation):
    # Returned directly so it skips the custom exception handler wrapper.
    return Response(overload_payload(evaluation), status=status.HTTP_409_CONFLICT)
