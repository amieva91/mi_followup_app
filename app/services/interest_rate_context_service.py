"""
Actualización diaria de contexto de tipos: Euribor 12M (API BCE) y futuro ESR=F (Yahoo).
Ejecutar 1×/día, p. ej.: `0 7 * * * cd /var/www/followup && ./venv/bin/python scripts/refresh_interest_rate_context_snapshot.py`
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import requests

from app import db
from app.models.interest_rate_context import InterestRateContextSnapshot
from app.services.mortgage_simulation_service import (
    CHART_API_BASE,
    CHART_API_HEADERS,
)

logger = logging.getLogger(__name__)

BCE_EURIBOR_12M_URL = (
    "https://data-api.ecb.europa.eu/service/data/"
    "FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"
)
ESR_F_YAHOO_TICKER = "ESR=F"

TREND_ALCISTA = "alcista"
TREND_BAJISTA = "bajista"
TREND_ESTABLE = "estable"
TREND_DESCONOCIDO = "desconocido"

# Variación mínima en puntos porcentuales para no marcar ruido como tendencia
_TREND_EPS_PERCENT = 0.02


def _implied_percent_from_future_price(price: float) -> float:
    return max(0.0, round(100.0 - float(price), 6))


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
        # Una sola observación habitualmente con clave "0"
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


def fetch_yahoo_esr_f() -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Precio del futuro ESR=F y tipo implícito ≈ 100 − precio (%).
    Devuelve (precio, implied_percent, error).
    """
    try:
        url = f"{CHART_API_BASE}/{ESR_F_YAHOO_TICKER}"
        r = requests.get(
            url,
            headers={
                **CHART_API_HEADERS,
                "Accept": "application/json",
                "Referer": "https://finance.yahoo.com/",
            },
            params={"range": "1mo", "interval": "1d"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        res = (data.get("chart") or {}).get("result") or []
        if not res:
            return None, None, "chart sin result"
        block = res[0]
        meta = block.get("meta") or {}
        for key in ("regularMarketPrice", "chartPreviousClose"):
            px = meta.get(key)
            if px is not None and isinstance(px, (int, float)) and float(px) > 0:
                p = float(px)
                return p, _implied_percent_from_future_price(p), None
        quotes = (block.get("indicators") or {}).get("quote") or [{}]
        closes = (quotes[0] or {}).get("close") or []
        for v in reversed(closes):
            if v is not None and isinstance(v, (int, float)) and float(v) > 0:
                p = float(v)
                return p, _implied_percent_from_future_price(p), None
    except Exception as e:
        logger.warning("Yahoo ESR=F fetch failed: %s", e)
        return None, None, str(e)[:500]
    return None, None, "sin precio en chart"


def _trend_vs_previous(
    current_bce: Optional[float], prev_bce: Optional[float]
) -> str:
    if current_bce is None or prev_bce is None:
        return TREND_DESCONOCIDO
    delta = float(current_bce) - float(prev_bce)
    if delta > _TREND_EPS_PERCENT:
        return TREND_ALCISTA
    if delta < -_TREND_EPS_PERCENT:
        return TREND_BAJISTA
    return TREND_ESTABLE


def refresh_snapshot() -> InterestRateContextSnapshot:
    """
    Obtiene BCE + Yahoo, calcula spread y tendencia respecto al snapshot anterior
    (mismo criterio: variación del Euribor 12M oficial).
    """
    bce_pct, bce_period, bce_err = fetch_bce_euribor_12m()
    yahoo_px, yahoo_impl, yahoo_err = fetch_yahoo_esr_f()

    spread = None
    if bce_pct is not None and yahoo_impl is not None:
        spread = round(float(yahoo_impl) - float(bce_pct), 6)

    prev = (
        InterestRateContextSnapshot.query.order_by(
            InterestRateContextSnapshot.fetched_at.desc()
        ).first()
    )
    prev_bce = float(prev.bce_euribor_12m_percent) if prev and prev.bce_euribor_12m_percent is not None else None
    trend = _trend_vs_previous(bce_pct, prev_bce)

    row = InterestRateContextSnapshot(
        fetched_at=datetime.utcnow(),
        bce_euribor_12m_percent=Decimal(str(bce_pct)) if bce_pct is not None else None,
        bce_time_period=bce_period,
        yahoo_esr_f_price=Decimal(str(yahoo_px)) if yahoo_px is not None else None,
        yahoo_implied_percent=Decimal(str(yahoo_impl)) if yahoo_impl is not None else None,
        spread_implied_minus_bce=Decimal(str(spread)) if spread is not None else None,
        trend_label=trend,
        bce_fetch_error=bce_err,
        yahoo_fetch_error=yahoo_err,
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
