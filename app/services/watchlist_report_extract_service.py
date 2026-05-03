"""
Extrae con Gemini Flash los 5 campos manuales de watchlist desde el markdown del informe.
Solo escribe en BD donde el origen del campo no es 'user'.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _parse_json_object(text: str) -> Optional[dict]:
    if not text or not str(text).strip():
        return None
    s = str(text).strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.I)
    if fence:
        s = fence.group(1).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def extract_watchlist_fields_from_report_md(report_markdown: str) -> Dict[str, Any]:
    """
    Llama a Gemini Flash para obtener JSON con los 5 campos (null si no consta).
    """
    from app.services.gemini_service import GeminiServiceError, _get_api_key, _get_model_flash

    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError("GEMINI_API_KEY no configurada")

    body = (report_markdown or "")[:120000]
    prompt = f"""Eres un extractor estricto. Tienes un informe de investigación en markdown (puede incluir la sección "Datos watchlist (extracción)").

Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni texto adicional, con exactamente estas claves:
- "next_earnings_date": string en formato YYYY-MM-DD o null
- "per_ntm": número o null
- "ntm_dividend_yield": número (porcentaje como número, ej. 2.5 para 2,5%) o null
- "eps": número o null
- "cagr_revenue_yoy": número (porcentaje como número) o null

Reglas:
- null si el informe no da un valor claro y explícito para esa magnitud.
- No inventes ni estimes: solo copia o deriva de cifras explícitas del texto.
- Si hay conflicto entre secciones, prioriza la sección "Datos watchlist (extracción)" si existe.

Informe:
---
{body}
---
"""

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=_get_model_flash(),
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1024),
    )
    raw = (resp.text or "").strip() if resp else ""
    data = _parse_json_object(raw)
    if not data:
        logger.warning("extract_watchlist_fields: no se pudo parsear JSON de la respuesta")
        return {}
    out = {}
    for key in (
        "next_earnings_date",
        "per_ntm",
        "ntm_dividend_yield",
        "eps",
        "cagr_revenue_yoy",
    ):
        if key not in data:
            out[key] = None
            continue
        v = data.get(key)
        if v in (None, "", "null", "no disponible", "n/d", "N/A"):
            out[key] = None
        else:
            out[key] = v
    return out


def apply_extracted_watchlist_fields(
    user_id: int,
    asset_id: int,
    extracted: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Aplica valores extraídos al registro Watchlist del usuario/asset.
    No toca campos con origen 'user'. Recalcula métricas derivadas.
    Retorna dict con claves actualizadas (información para logs/UI).
    """
    from app import db
    from app.models import Watchlist, PortfolioHolding
    from app.services.currency_service import convert_to_eur
    from app.services.watchlist_metrics_service import WatchlistMetricsService
    from app.services.watchlist_service import WatchlistService

    wl = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()
    if not wl:
        return {"skipped": True, "reason": "no_watchlist_row"}

    sources = wl.get_manual_field_sources_dict()
    applied = {}
    src_updates = {}

    if wl.get_manual_field_source("next_earnings_date") != "user":
        raw_d = extracted.get("next_earnings_date")
        if raw_d and isinstance(raw_d, str):
            try:
                wl.next_earnings_date = datetime.strptime(raw_d[:10], "%Y-%m-%d").date()
                applied["next_earnings_date"] = str(wl.next_earnings_date)
                src_updates["next_earnings_date"] = "ai"
            except (ValueError, TypeError):
                pass

    for key in ("per_ntm", "ntm_dividend_yield", "eps", "cagr_revenue_yoy"):
        if wl.get_manual_field_source(key) == "user":
            continue
        v = extracted.get(key)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        setattr(wl, key, fv)
        applied[key] = fv
        src_updates[key] = "ai"

    if src_updates:
        wl.merge_manual_field_sources(src_updates)

    # Recalcular métricas calculadas
    config = WatchlistService.get_or_create_config(user_id)
    current_value_eur = None
    holding = (
        PortfolioHolding.query.filter_by(user_id=user_id, asset_id=asset_id)
        .filter(PortfolioHolding.quantity > 0)
        .first()
    )
    if holding:
        cost_eur = convert_to_eur(holding.total_cost, holding.asset.currency)
        if holding.asset.current_price:
            current_value_local = holding.quantity * holding.asset.current_price
            current_value_eur = convert_to_eur(current_value_local, holding.asset.currency)
        else:
            current_value_eur = cost_eur

    WatchlistMetricsService.update_all_metrics(wl, config, current_value_eur=current_value_eur)
    db.session.commit()
    return {"applied": applied, "skipped": False}


def try_apply_report_to_watchlist(user_id: int, asset_id: int, report_markdown: str) -> None:
    """No lanza si falla extracción: solo log."""
    try:
        extracted = extract_watchlist_fields_from_report_md(report_markdown)
        if not extracted:
            return
        apply_extracted_watchlist_fields(user_id, asset_id, extracted)
    except Exception as e:
        logger.exception("try_apply_report_to_watchlist: %s", e)
