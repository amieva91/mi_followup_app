"""Constantes y helpers para edición de series recurrentes (gastos/ingresos)."""

from datetime import date
from typing import Optional

RECURRENCE_EDIT_SCOPES = frozenset({"series", "future", "entry"})


def parse_pivot_date(value) -> Optional[date]:
    if not value or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None
