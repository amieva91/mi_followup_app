"""
Registro de llamadas a APIs externas para el panel de administración.
Retención máxima: 6 meses.
"""
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import or_
from app import db
from app.models import ApiCallLog


RETENTION_MONTHS = 6


def delete_logs_older_than_retention(months: int = RETENTION_MONTHS) -> int:
    """Elimina registros más antiguos que el período de retención. Devuelve número de filas borradas."""
    since = datetime.utcnow() - timedelta(days=months * 31)
    deleted = ApiCallLog.query.filter(ApiCallLog.called_at < since).delete()
    db.session.commit()
    return deleted


def log_api_call(
    api_name: str,
    endpoint_or_operation: Optional[str] = None,
    response_status: Optional[int] = None,
    value_reported: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Registra una llamada a una API externa (Yahoo, exchangerate, etc.)."""
    try:
        entry = ApiCallLog(
            api_name=api_name,
            endpoint_or_operation=endpoint_or_operation,
            response_status=response_status,
            value_reported=value_reported,
            user_id=user_id,
            extra=extra,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # No fallar la petición principal si el log falla
        pass


def get_api_metrics(days: int = 30) -> Dict[str, Any]:
    """
    Métricas de llamadas a API: por día, media diaria, por mes, media mensual.
    days: número de días hacia atrás a considerar.
    """
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        ApiCallLog.query.filter(ApiCallLog.called_at >= since)
        .order_by(ApiCallLog.called_at.desc())
        .all()
    )

    by_day: Dict[date, int] = {}
    by_month: Dict[str, int] = {}  # key "YYYY-MM"

    for log in logs:
        d = log.called_at.date()
        by_day[d] = by_day.get(d, 0) + 1
        month_key = d.strftime("%Y-%m")
        by_month[month_key] = by_month.get(month_key, 0) + 1

    total = len(logs)
    num_days = len(by_day) or 1
    num_months = len(by_month) or 1
    avg_per_day = round(total / num_days, 1)
    avg_per_month = round(total / num_months, 1)

    # Por API
    by_api: Dict[str, int] = {}
    for log in logs:
        by_api[log.api_name] = by_api.get(log.api_name, 0) + 1

    return {
        "total_calls": total,
        "days_considered": days,
        "calls_per_day": dict(sorted(by_day.items(), reverse=True)),
        "avg_per_month": avg_per_month,
        "calls_per_month": dict(sorted(by_month.items(), reverse=True)),
        "avg_per_day": avg_per_day,
        "by_api": by_api,
    }


def get_api_calls_chart_data(days: int = 30) -> Dict[str, List]:
    """
    Serie diaria de llamadas para la gráfica: labels (fechas) y data (número de llamadas por día).
    Rango: desde (hoy - days + 1) hasta hoy (incluido), para que el último día sea siempre hoy.
    """
    today = datetime.utcnow().date()
    start = today - timedelta(days=days - 1)
    metrics = get_api_metrics(days=days)
    by_day = metrics.get("calls_per_day", {})

    labels = []
    data = []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%d/%m"))
        data.append(by_day.get(d, 0))
    return {"labels": labels, "data": data}


def get_api_names_distinct() -> List[str]:
    """Lista de nombres de API únicos para filtros."""
    rows = db.session.query(ApiCallLog.api_name).distinct().order_by(ApiCallLog.api_name).all()
    return [r[0] for r in rows if r[0]]


def get_api_logs_filtered(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[str] = None,
    api_name: Optional[str] = None,
    endpoint_substring: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 500,
) -> List[ApiCallLog]:
    """
    Lista de llamadas con filtros.
    status: 'success' (200), 'error' (no 200 o null), o None = todos.
    """
    q = ApiCallLog.query
    if date_from:
        q = q.filter(ApiCallLog.called_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.filter(ApiCallLog.called_at < datetime.combine(date_to, datetime.min.time()) + timedelta(days=1))
    if status == "success":
        q = q.filter(ApiCallLog.response_status == 200)
    elif status == "error":
        q = q.filter(or_(ApiCallLog.response_status != 200, ApiCallLog.response_status.is_(None)))
    if api_name:
        q = q.filter(ApiCallLog.api_name == api_name)
    if endpoint_substring:
        q = q.filter(ApiCallLog.endpoint_or_operation.ilike(f"%{endpoint_substring}%"))
    if user_id is not None:
        if user_id == 0:
            q = q.filter(ApiCallLog.user_id.is_(None))
        else:
            q = q.filter(ApiCallLog.user_id == user_id)
    q = q.order_by(ApiCallLog.called_at.desc()).limit(limit)
    return q.all()
