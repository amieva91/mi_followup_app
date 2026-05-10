"""
Rellena campos editables de watchlist a partir del texto devuelto por **Flash / Deep Research**.

Flujo:
1. Si el markdown incluye un bloque ``json`` con claves conocidas (briefing en
   ``watchlist_ia_template``), se parsea aquí **sin llamar a Flash**.
2. Si no, **Gemini Flash** lee el markdown y devuelve el mismo JSON (normalizador/rescate).

Los valores se escriben con :func:`apply_extracted_watchlist_fields`, que **nunca** sustituye campos con origen ``user``.
"""
import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, Optional

from app.services.watchlist_ia_template import watchlist_ia_all_keys_for_mode

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


def _utc_today() -> date:
    return datetime.utcnow().date()


def _sanitize_next_earnings_candidate(raw: Any) -> Any:
    """
    «Próximos» resultados: descarta fechas estrictamente anteriores a hoy (UTC),
    típico sesgo del modelo (p. ej. año 2024 en 2026). Devuelve 'YYYY-MM-DD' o None.
    """
    if raw in (None, "", "null", "no disponible", "n/d", "N/A"):
        return None
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    if len(s) < 10:
        return None
    try:
        d = datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    today = _utc_today()
    if d < today:
        logger.info(
            "watchlist: next_earnings_date descartada (anterior a hoy UTC %s): %s",
            today.isoformat(),
            s[:10],
        )
        return None
    return s[:10]


def _normalize_watchlist_extract(data: dict, mode: str) -> Dict[str, Any]:
    """Normaliza claves del modo; valores desconocidos → None donde aplique."""
    keys = watchlist_ia_all_keys_for_mode(mode)
    out: Dict[str, Any] = {}
    for key in keys:
        if key not in data:
            out[key] = None
            continue
        v = data.get(key)
        if v in (None, "", "null", "no disponible", "n/d", "N/A"):
            out[key] = None
        elif key == "next_earnings_date":
            out[key] = _sanitize_next_earnings_candidate(v)
        elif key == "reit_leverage_kind":
            if isinstance(v, str) and v.strip():
                out[key] = v.strip()[:32]
            else:
                out[key] = None
        else:
            out[key] = v
    return out


def _try_inline_json_from_report_md(
    report_markdown: str, mode: str
) -> Optional[Dict[str, Any]]:
    """
    Busca bloques ```json en el markdown.
    Devuelve dict normalizado si hay al menos una clave conocida con contenido parseable.
    """
    if not report_markdown or not str(report_markdown).strip():
        return None
    keys_known = set(watchlist_ia_all_keys_for_mode(mode))
    for fence in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", report_markdown, re.I):
        inner = fence.group(1).strip()
        data = _parse_json_object(inner)
        if not data:
            continue
        if not any(k in data for k in keys_known):
            continue
        norm = _normalize_watchlist_extract(data, mode)
        if any(norm.get(k) is not None for k in keys_known):
            return norm
    return None


def extract_watchlist_fields_from_report_md(
    report_markdown: str,
    *,
    user_id: Optional[int] = None,
    asset_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Obtiene JSON con claves del briefing: primero desde bloque embebido; si no, Gemini Flash.

    Si se pasan ``user_id`` y ``asset_id``, el conjunto de claves sigue el modo de valoración
    (general / banks / realestate). Si no, se usa modo ``general`` (solo núcleo + extras general).
    """
    from app.services.valuation_mode_service import (
        resolve_watchlist_valuation_mode_for_user_asset,
    )

    if user_id and asset_id:
        mode = resolve_watchlist_valuation_mode_for_user_asset(int(user_id), int(asset_id))
    else:
        mode = "general"

    inline = _try_inline_json_from_report_md(report_markdown, mode)
    if inline is not None:
        return inline

    from app.services.gemini_service import GeminiServiceError, _get_api_key, _get_model_flash

    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError("GEMINI_API_KEY no configurada")

    body = (report_markdown or "")[:120000]
    ref_today = datetime.utcnow().strftime("%Y-%m-%d")
    keys = watchlist_ia_all_keys_for_mode(mode)
    keys_bullet = "\n".join(f'- "{k}"' for k in keys)
    prompt = f"""Eres un extractor estricto. Tienes un informe de investigación en markdown (puede incluir la sección "Datos watchlist (extracción)").

Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni texto adicional, con exactamente estas claves:
{keys_bullet}

Reglas de tipos:
- "next_earnings_date": string YYYY-MM-DD o null
- "reit_leverage_kind": string breve (máx. 32 caracteres) o null
- resto numérico cuando aplique: número o null (porcentajes como número, ej. 2.5 para 2,5%)
- null si el informe no da un valor claro y explícito para esa magnitud
- No inventes ni estimes: solo copia o deriva de cifras explícitas del texto
- Si hay conflicto entre secciones, prioriza "Datos watchlist (extracción)" si existe
- **next_earnings_date** = solo la próxima divulgación **en el futuro** respecto a {ref_today} (UTC). Fechas anteriores → null

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
        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=2048),
    )
    raw = (resp.text or "").strip() if resp else ""
    data = _parse_json_object(raw)
    if not data:
        logger.warning("extract_watchlist_fields: no se pudo parsear JSON de la respuesta")
        return {}
    return _normalize_watchlist_extract(data, mode)


def apply_extracted_watchlist_fields(
    user_id: int,
    asset_id: int,
    extracted: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Aplica valores extraídos al registro Watchlist del usuario/asset.
    No modifica campos cuyo origen en ``manual_field_sources`` es ``user``. Recalcula métricas derivadas.
    """
    from app import db
    from app.models import Watchlist, PortfolioHolding
    from app.services.currency_service import convert_to_eur
    from app.services.valuation_mode_service import (
        resolve_watchlist_valuation_mode_for_user_asset,
    )
    from app.services.watchlist_metrics_service import WatchlistMetricsService
    from app.services.watchlist_service import WatchlistService

    wl = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()
    if not wl:
        return {"skipped": True, "reason": "no_watchlist_row"}

    mode = resolve_watchlist_valuation_mode_for_user_asset(user_id, asset_id)
    allowed = frozenset(watchlist_ia_all_keys_for_mode(mode))

    applied = {}
    src_updates = {}

    for key in allowed:
        if wl.get_manual_field_source(key) == "user":
            continue
        if key not in extracted:
            continue
        raw = extracted.get(key)
        if raw in (None, "", "null", "no disponible", "n/d", "N/A"):
            continue

        if key == "next_earnings_date":
            san = _sanitize_next_earnings_candidate(raw)
            if san:
                try:
                    wl.next_earnings_date = datetime.strptime(san, "%Y-%m-%d").date()
                    applied["next_earnings_date"] = str(wl.next_earnings_date)
                    src_updates["next_earnings_date"] = "ai"
                except (ValueError, TypeError):
                    pass
            continue

        coerced = WatchlistService.coerce_watchlist_manual_value(key, raw)
        if coerced is None:
            continue
        setattr(wl, key, coerced)
        applied[key] = coerced
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

    WatchlistMetricsService.update_all_metrics(
        wl, config, current_value_eur=current_value_eur, asset=wl.asset
    )
    db.session.commit()
    return {"applied": applied, "skipped": False}


def try_apply_report_to_watchlist(user_id: int, asset_id: int, report_markdown: str) -> None:
    """No lanza si falla extracción: solo log."""
    try:
        from app.services.valuation_mode_service import (
            resolve_watchlist_valuation_mode_for_user_asset,
        )

        extracted = extract_watchlist_fields_from_report_md(
            report_markdown, user_id=user_id, asset_id=asset_id
        )
        if not extracted:
            return
        mode = resolve_watchlist_valuation_mode_for_user_asset(user_id, asset_id)
        allowed = frozenset(watchlist_ia_all_keys_for_mode(mode))
        if not any(extracted.get(k) is not None for k in allowed):
            logger.info(
                "watchlist extract: sin valores no nulos tras normalizar (asset_id=%s); "
                "suele indicar que el modelo no encontró cifras verificables, no un fallo de API.",
                asset_id,
            )
            return
        apply_extracted_watchlist_fields(user_id, asset_id, extracted)
    except Exception as e:
        logger.exception("try_apply_report_to_watchlist: %s", e)
