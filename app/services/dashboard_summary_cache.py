"""
Cache del resumen del dashboard principal (/dashboard).
TTL 15 min; se invalida al cambiar transacciones, gastos, ingresos, bancos, inmuebles, deudas.
"""
import copy
import json
from datetime import date, datetime, timezone
from app import db
from app.models.dashboard_summary_cache import DashboardSummaryCache


def _make_json_serializable(obj):
    """Convierte recursivamente date/datetime a string ISO para que el JSON sea serializable."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]
    return obj


def _utc_iso_z(dt: datetime) -> str:
    """
    ISO-8601 UTC con sufijo 'Z' (evita que el frontend lo interprete como hora local).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

def _now_signature(data: dict) -> str:
    """
    Firma estable de la parte NOW que se pinta en el dashboard.
    Sirve para actualizar meta.version/_now_cached_at SOLO cuando cambian valores.
    """
    try:
        b = data.get("breakdown") or {}
        pd = data.get("portfolio_details") or {}
        cd = data.get("crypto_details") or {}
        md = data.get("metales_details") or {}
        rd = data.get("real_estate_details") or {}
        dd = data.get("debt_details") or {}
        mi = data.get("market_indices") or []
        mi_sig: list[tuple] = []
        for x in mi:
            if not isinstance(x, dict):
                continue
            dcp = x.get("day_change_percent")
            lc = x.get("last_close")
            try:
                dcp_r = round(float(dcp), 2) if dcp is not None else None
            except (TypeError, ValueError):
                dcp_r = None
            try:
                lc_r = round(float(lc), 4) if lc is not None else None
            except (TypeError, ValueError):
                lc_r = None
            mi_sig.append((str(x.get("name") or ""), dcp_r, lc_r))

        payload = {
            "net_worth": round(float(data.get("net_worth") or 0), 2),
            "changes": data.get("changes") or {},
            "breakdown": {
                "cash": round(float(b.get("cash") or 0), 2),
                "portfolio": round(float(b.get("portfolio") or 0), 2),
                "crypto": round(float(b.get("crypto") or 0), 2),
                "metales": round(float(b.get("metales") or 0), 2),
                "real_estate": round(float(b.get("real_estate") or 0), 2),
                "debt": round(float(b.get("debt") or 0), 2),
            },
            "portfolio_total": round(float(pd.get("total_value") or 0), 2),
            "crypto_total": round(float(cd.get("total_value") or 0), 2),
            "metales_total": round(float(md.get("total_value") or 0), 2),
            "real_estate_total": round(float(rd.get("total_value") or 0), 2),
            "debt_total": round(float(dd.get("total_debt") or 0), 2),
            "market_indices": mi_sig,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        # Fallback: forzar update si algo raro ocurre
        return str(datetime.utcnow().timestamp())

class DashboardSummaryCacheService:
    @staticmethod
    def get(user_id: int):
        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if not cache or not cache.is_valid:
            if cache:
                db.session.delete(cache)
                db.session.commit()
            return None
        cached = cache.cached_data or {}
        meta_pre = dict(cached.get("meta") or {})
        # Tras editar saldos de meses pasados se marca needs_full_rebuild; servir ese HIST
        # congelado hace que el efectivo del gráfico no coincida con BankBalance ni con el
        # ajuste de reconciliación (que sí lee la BD en vivo). Forzar miss hasta rebuild.
        if meta_pre.get("needs_full_rebuild"):
            return None
        data = cached.copy()
        data['_from_cache'] = True
        # Siempre exponer timestamp UTC explícito
        data['_cached_at'] = _utc_iso_z(cache.created_at)
        # Para compatibilidad, asegurar que meta._cached_at exista en la respuesta
        meta = dict(data.get("meta") or {})
        if not meta.get("_cached_at"):
            meta["_cached_at"] = data["_cached_at"]
        # El polling del frontend usa meta.version; filas antiguas pueden no tenerla
        if meta.get("version") is None and cache.created_at:
            meta["version"] = int(cache.created_at.timestamp() * 1000)
        elif meta.get("version") is None:
            meta["version"] = int(datetime.utcnow().timestamp() * 1000)
        data["meta"] = meta
        return data

    @staticmethod
    def set(user_id: int, data: dict):
        clean = {k: v for k, v in data.items() if not str(k).startswith("_")}
        clean = _make_json_serializable(clean)

        # Marcar versión del snapshot de dashboard (para futuros usos en frontend / jobs)
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        meta = dict(clean.get("meta") or {})
        if "version" not in meta:
            # Milisegundos para evitar colisiones si hay varias escrituras en el mismo segundo
            meta["version"] = int(now.timestamp() * 1000)
        # Timestamp consistente para el frontend
        meta["_cached_at"] = _utc_iso_z(now)
        # Para el contador de "Actualizado hace X min" (NOW)
        meta["_now_cached_at"] = meta["_cached_at"]
        # Firma NOW para detectar cambios
        try:
            meta["now_sig"] = _now_signature(clean)
        except Exception:
            meta.pop("now_sig", None)
        # Cualquier marca de reconstrucción pendiente deja de aplicar tras un set completo
        meta.pop("needs_full_rebuild", None)
        clean["meta"] = meta

        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if cache:
            cache.cached_data = clean
            cache.created_at = now.replace(tzinfo=None)
            cache.expires_at = DashboardSummaryCache.get_default_expiry()
        else:
            cache = DashboardSummaryCache(
                user_id=user_id,
                cached_data=clean,
                created_at=now.replace(tzinfo=None),
                expires_at=DashboardSummaryCache.get_default_expiry(),
            )
            db.session.add(cache)
        db.session.commit()
        return cache

    @staticmethod
    def invalidate(user_id: int) -> bool:
        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if cache:
            data = dict(cache.cached_data or {})
            meta = dict(data.get("meta") or {})
            # Marcar que hace falta una reconstrucción completa de HIST en background,
            # pero mantener el snapshot actual para que el usuario vea datos viejos
            # hasta que el polling lo renueve.
            meta["needs_full_rebuild"] = True
            data["meta"] = meta
            cache.cached_data = _make_json_serializable(data)
            db.session.commit()
            return True
        return False

    @staticmethod
    def touch_for_dates(user_id: int, dates=None, month_refs=None) -> None:
        """
        Criterio unificado de invalidación basado en fechas afectadas.

        - Si TODAS las fechas/meses son "hoy" / mes actual -> recompute_current_from_cache
        - Si alguna fecha/mes es pasada (≠ hoy / ≠ mes actual) -> invalidate completo

        Parámetros:
        - dates: iterable de datetime.date o datetime (se usa .date())
        - month_refs: iterable de tuplas (year, month) para casos tipo bancos,
          donde solo se conoce año/mes (sin día).
        """
        today = datetime.utcnow().date()

        any_past = False
        any_today_or_current = False

        if dates:
            for d in dates:
                if isinstance(d, datetime):
                    d = d.date()
                if not isinstance(d, date):
                    continue
                if d == today:
                    any_today_or_current = True
                elif d < today:
                    any_past = True

        if month_refs:
            for year, month in month_refs:
                try:
                    year = int(year)
                    month = int(month)
                except (TypeError, ValueError):
                    continue
                if year == today.year and month == today.month:
                    any_today_or_current = True
                else:
                    any_past = True

        # Sin información -> comportamiento conservador: invalidar completo
        if not any_today_or_current and not any_past:
            DashboardSummaryCacheService.invalidate(user_id)
            return

        if any_past:
            DashboardSummaryCacheService.invalidate(user_id)
        else:
            # Solo hoy / mes actual -> intentar recompute parcial
            updated = DashboardSummaryCacheService.recompute_current_from_cache(user_id)
            if updated is None:
                DashboardSummaryCacheService.invalidate(user_id)

    @staticmethod
    def recompute_current_from_cache(user_id: int) -> dict | None:
        """
        Recalcula NOW (breakdown, detalles, widgets) y alinea el ÚLTIMO punto del
        histórico con ese breakdown; meses anteriores no se recalculan.

        Devuelve el diccionario cacheado actualizado, o None si no es posible
        (por ejemplo, si falta history).
        """
        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if not cache or not cache.cached_data:
            return None

        data = dict(cache.cached_data)
        prev_meta = dict(data.get("meta") or {})

        # Si el snapshot pide una reconstrucción completa (cambio en HIST),
        # delegar en get_dashboard_summary + set y salir.
        meta = dict(data.get("meta") or {})
        if meta.get("needs_full_rebuild"):
            from app.services import net_worth_service as nws

            summary = nws.get_dashboard_summary(user_id)
            DashboardSummaryCacheService.set(user_id, summary)
            return summary

        # Intentar obtener histórico desde history_block; si no, usar history plano
        history_block = data.get("history_block") or {}
        history = history_block.get("history") or data.get("history") or []
        if not history:
            return None

        # Importar aquí para evitar ciclos de importación y recalcular SOLO la parte "actual"
        from app.services import net_worth_service as nws

        # Recalcular breakdown y detalles actuales (NOW), reutilizando histórico (HIST)
        breakdown = nws.get_net_worth_breakdown(user_id)
        data["breakdown"] = breakdown
        data["cash_details"] = nws.get_cash_details(user_id)
        data["portfolio_details"] = nws.get_portfolio_details(user_id)
        data["crypto_details"] = nws.get_crypto_details(user_id)
        data["metales_details"] = nws.get_metales_details(user_id)
        data["real_estate_details"] = nws.get_real_estate_details(user_id)
        data["debt_details"] = nws.get_debt_details(user_id)

        # Métricas derivadas de NOW (no tocan history_block)
        data["savings"] = nws.get_savings_rate(user_id, months=12)
        data["projections"] = nws.get_net_worth_projection(user_id)
        data["income_expense_monthly"] = nws.get_income_expense_by_month(user_id, months=12)
        data["top_expenses"] = nws.get_top_expenses_month(user_id)
        data["upcoming_payments"] = nws.get_upcoming_payments(user_id)
        data["investments_summary"] = nws.get_investments_summary(user_id)
        data["recent_transactions"] = nws.get_recent_transactions(user_id)
        data["currency_exposure"] = nws.get_currency_exposure(user_id)
        data["year_comparison"] = nws.get_year_comparison(user_id)
        data["health_score"] = nws.get_financial_health_score(user_id)
        try:
            from app.services.recommendation_service import RecommendationService
            data["recommendations"] = RecommendationService.build_for_dashboard(
                user_id, health_score=data["health_score"]
            )
        except Exception:
            data["recommendations"] = data.get("recommendations") or []
        from app.services.income_expense_aggregator import (
            get_expense_category_summary_with_adjustment,
            get_income_category_summary_with_adjustment,
        )
        data["expense_category_summary"] = get_expense_category_summary_with_adjustment(
            user_id, months=12
        )
        data["income_category_summary"] = get_income_category_summary_with_adjustment(
            user_id, months=12
        )
        data["top_movers"] = nws.get_top_movers_for_user(user_id, limit=5)
        from app.services.portfolio_benchmarks_cache import get_market_indices_snapshot

        data["market_indices"] = get_market_indices_snapshot(user_id)
        data["commodities"] = nws.get_commodities_snapshot(user_id)

        # DAY % y EUR inversiones (NOW)
        # Importante: más abajo se reemplaza data["changes"] con current_block["changes"],
        # así que guardamos los valores para reinyectarlos después.
        day_pct = None
        day_eur = None
        try:
            day_inv = nws.get_investments_day_change(user_id)
            if day_inv:
                day_pct, day_eur = day_inv
            if isinstance(data.get("changes"), dict):
                data["changes"]["day_pct"] = day_pct
                data["changes"]["day_eur"] = day_eur
        except Exception:
            if isinstance(data.get("changes"), dict):
                data["changes"]["day_pct"] = None
                data["changes"]["day_eur"] = None

        # Solo actualizar el ÚLTIMO punto del histórico (mes actual / “ahora”) con el breakdown
        # recién calculado; el resto de meses permanece congelado (HIST).
        last = copy.deepcopy(history[-1])
        cash = round(float(breakdown["cash"]), 2)
        port = round(float(breakdown["portfolio"]), 2)
        crypto = round(float(breakdown["crypto"]), 2)
        metales = round(float(breakdown["metales"]), 2)
        re_est = round(float(breakdown.get("real_estate") or 0), 2)
        debt = round(float(breakdown["debt"]), 2)
        nw = round(float(breakdown["net_worth"]), 2)
        last.update({
            "cash": cash,
            "broker_total": port,
            "crypto": crypto,
            "metales": metales,
            "real_estate": re_est,
            "investments": round(port + crypto + metales + re_est, 2),
            "debt": debt,
            "net_worth": nw,
        })
        new_history = list(history[:-1]) + [last]
        data["history"] = new_history
        hb = data.get("history_block")
        if isinstance(hb, dict):
            hb = copy.deepcopy(hb)
            hb["history"] = new_history
            data["history_block"] = hb

        # Construir bloque "actual" con el histórico ya alineado al último punto
        current_block = nws._build_dashboard_current_from_history(breakdown, new_history)
        current_block["current_point"] = last

        # Actualizar campos principales que el dashboard ya usa
        data["net_worth"] = current_block["net_worth"]
        data["changes"] = current_block["changes"]
        data["current_block"] = current_block

        # Reinyectar day_pct / day_eur (evita que se pierdan por el overwrite de "changes")
        if isinstance(data.get("changes"), dict):
            data["changes"]["day_pct"] = day_pct
            data["changes"]["day_eur"] = day_eur
        if isinstance(current_block.get("changes"), dict):
            current_block["changes"]["day_pct"] = day_pct
            current_block["changes"]["day_eur"] = day_eur

        # Actualizar metadatos y TTL:
        # - version/_now_cached_at: SOLO si cambió NOW (firma distinta).
        # - _cached_at: NO se toca aquí; representa la edad del HIST.
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        meta = dict(prev_meta)
        new_sig = _now_signature(data)
        if new_sig != (prev_meta.get("now_sig") or ""):
            meta["version"] = int(now.timestamp() * 1000)
            meta["_now_cached_at"] = _utc_iso_z(now)
            meta["now_sig"] = new_sig
        data["meta"] = meta

        cache.cached_data = _make_json_serializable(data)
        # NO tocar created_at aquí: created_at representa la edad del snapshot completo (HIST).
        # Si lo actualizamos en cada recompute NOW (polling), el frontend siempre mostrará
        # "Actualizado hace menos de 1 min".
        cache.expires_at = DashboardSummaryCache.get_default_expiry()
        db.session.commit()

        return data
