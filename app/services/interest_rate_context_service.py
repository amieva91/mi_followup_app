"""
Actualización periódica del Euribor 12M vía API pública del BCE (jsondata).
Ejecutar 1×/día como usuario del servicio (p. ej. followup), ver
`scripts/refresh_interest_rate_context_snapshot.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import requests

from app import db
from app.models.interest_rate_context import InterestRateContextSnapshot

logger = logging.getLogger(__name__)

BCE_EURIBOR_12M_URL = (
    "https://data-api.ecb.europa.eu/service/data/"
    "FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"
)


def fetch_bce_euribor_12m() -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Última observación mensual Euribor 12M (media del período, BCE).
    Devuelve (porcentaje, TIME_PERIOD tipo YYYY-MM, mensaje_error).
    """
    try:
        r = requests.get(
            BCE_EURIBOR_12M_URL,
            params={"lastNObservations": "1", "format": "jsondata"},
            headers={"Accept": "application/json"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("BCE Euribor fetch failed: %s", e)
        return None, None, str(e)[:500]

    pct, period, err = _parse_ecb_jsondata_euribor(data)
    if err:
        logger.warning("BCE Euribor parse failed: %s", err)
        return None, None, err[:500]
    return pct, period, None


def _parse_ecb_jsondata_euribor(data: Dict[str, Any]) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    try:
        datasets = data.get("dataSets") or []
        if not datasets:
            return None, None, "dataSets vacío"
        series = datasets[0].get("series") or {}
        if not series:
            return None, None, "series vacío"
        first_series = next(iter(series.values()))
        observations = first_series.get("observations") or {}
        if not observations:
            return None, None, "observations vacío"
        obs_keys = sorted(observations.keys(), key=lambda k: int(k) if str(k).isdigit() else 0)
        raw = observations[obs_keys[0]]
        if not raw or raw[0] is None:
            return None, None, "valor observación vacío"
        value = float(raw[0])

        period = None
        structure = data.get("structure") or {}
        for dim in (structure.get("dimensions") or {}).get("observation") or []:
            if dim.get("id") == "TIME_PERIOD":
                vals = dim.get("values") or []
                if vals:
                    period = vals[0].get("id")
                break
        return value, period, None
    except Exception as e:
        return None, None, str(e)


def refresh_snapshot() -> InterestRateContextSnapshot:
    """Obtiene solo Euribor 12M (BCE) y persiste una fila."""
    bce_pct, bce_period, bce_err = fetch_bce_euribor_12m()

    row = InterestRateContextSnapshot(
        fetched_at=datetime.utcnow(),
        bce_euribor_12m_percent=Decimal(str(bce_pct)) if bce_pct is not None else None,
        bce_time_period=bce_period,
        yahoo_esr_f_price=None,
        yahoo_implied_percent=None,
        spread_implied_minus_bce=None,
        trend_label="desconocido",
        bce_fetch_error=bce_err,
        yahoo_fetch_error=None,
    )
    db.session.add(row)
    db.session.commit()
    return row


def get_latest_snapshot() -> Optional[InterestRateContextSnapshot]:
    return (
        InterestRateContextSnapshot.query.order_by(
            InterestRateContextSnapshot.fetched_at.desc()
        ).first()
    )
