"""
Rutas principales de la aplicación
"""
from flask import render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import func, extract
from app.routes import main_bp
from app import db
from app.models import Expense, Income, UserDashboardConfig, UserDashboardLayout, DEFAULT_WIDGETS, MODULES
from app.services.dashboard_onboarding_service import DashboardOnboardingService
from app.services.net_worth_service import get_dashboard_summary
from app.services.price_polling_service import get_updated_asset_ids_for_user


@main_bp.route('/')
def index():
    """Página de inicio"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con resumen de patrimonio"""
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    summary = DashboardSummaryCacheService.get(current_user.id)
    if summary is None:
        summary = get_dashboard_summary(current_user.id)
        DashboardSummaryCacheService.set(current_user.id, summary)
    
    # Obtener configuración de widgets del usuario
    widget_config = UserDashboardConfig.get_user_config(current_user.id)
    enabled_widgets = UserDashboardConfig.get_enabled_widgets(current_user.id)
    
    # Datos adicionales para widgets específicos
    now = datetime.now()

    onboarding = DashboardOnboardingService.build_state(current_user)
    for bucket in ("applicable_milestones", "completed_milestones", "pending_milestones", "newly_completed_milestones"):
        items = onboarding.get(bucket) or []
        for item in items:
            endpoint = item.get("endpoint")
            kwargs = item.get("endpoint_kwargs") or {}
            try:
                item["url"] = url_for(endpoint, **kwargs) if endpoint else "#"
            except Exception:
                item["url"] = "#"
    
    return render_template(
        'dashboard.html',
        summary=summary,
        onboarding=onboarding,
        modules=MODULES,
        enabled_module_keys=current_user.get_enabled_modules(),
        widget_config=widget_config,
        enabled_widgets=enabled_widgets,
        default_widgets=DEFAULT_WIDGETS,
        current_month_name=now.strftime('%B'),
        current_year=now.year
    )


@main_bp.route('/dashboard/onboarding/ack', methods=['POST'])
@login_required
def dashboard_onboarding_ack():
    data = request.get_json(silent=True) or {}
    milestones = data.get("milestones") or []
    if not isinstance(milestones, list):
        return jsonify({"success": False, "error": "Formato inválido"}), 400
    saved = DashboardOnboardingService.acknowledge_milestones(current_user.id, milestones)
    return jsonify({"success": True, "saved": saved}), 200


@main_bp.route('/dashboard/onboarding/modules', methods=['POST'])
@login_required
def dashboard_onboarding_modules():
    enabled = [k for k in MODULES.keys() if request.form.get(f'module_{k}') == 'on']
    if not enabled:
        flash('Debes mantener al menos un módulo activo.', 'warning')
        return redirect(url_for('main.dashboard'))
    current_user.enabled_modules = enabled
    db.session.commit()
    flash('Módulos actualizados. Las sugerencias se han ajustado.', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/api/price-updates')
@login_required
def api_price_updates():
    """
    Polling ligero: activos del usuario actualizados desde `since` (ISO).
    Sin recalcular dashboard. Primera petición sin `since` → lista vacía (evita flash al cargar).
    """
    view = (request.args.get('view') or '').strip().lower()
    updated_asset_ids = []
    since_param = request.args.get('since')
    since = None
    if since_param:
        try:
            since = datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            if since.tzinfo:
                since = since.replace(tzinfo=None)
            updated_asset_ids = get_updated_asset_ids_for_user(current_user.id, since)
        except (ValueError, TypeError):
            pass

    server_now = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    updates = {}
    if since is not None and updated_asset_ids:
        # Devolver valores actualizados según la vista (para repintar sin F5)
        from app.models.asset import Asset
        assets = Asset.query.filter(Asset.id.in_(updated_asset_ids)).all()
        asset_by_id = {a.id: a for a in assets}

        if view in ('portfolio', 'holdings'):
            # Calcular value/pnl en EUR desde holdings + Asset.current_price
            from app.models.portfolio import PortfolioHolding
            from app.services.currency_service import convert_to_eur

            rows = (
                db.session.query(PortfolioHolding)
                .filter(PortfolioHolding.user_id == current_user.id)
                .filter(PortfolioHolding.quantity > 0)
                .filter(PortfolioHolding.asset_id.in_(updated_asset_ids))
                .all()
            )
            agg = {}
            for h in rows:
                a = asset_by_id.get(h.asset_id) or h.asset
                if not a:
                    continue
                cur = a.currency or 'EUR'
                qty = float(h.quantity or 0)
                price_local = float(a.current_price or 0)
                cost_local = float(h.total_cost or 0)
                # Convertir a EUR
                price_eur = float(convert_to_eur(price_local, cur)) if price_local else 0.0
                cost_eur = float(convert_to_eur(cost_local, cur)) if cost_local else 0.0
                value_eur = qty * price_eur

                acc = agg.setdefault(h.asset_id, {'qty': 0.0, 'cost_eur': 0.0, 'value_eur': 0.0, 'currency': cur, 'price_local': price_local})
                acc['qty'] += qty
                acc['cost_eur'] += cost_eur
                acc['value_eur'] += value_eur
                acc['price_local'] = price_local

            for aid, d in agg.items():
                pl_eur = d['value_eur'] - d['cost_eur']
                pl_pct = (pl_eur / d['cost_eur'] * 100.0) if d['cost_eur'] else 0.0
                updates[str(aid)] = {
                    'price_local': d['price_local'],
                    'currency': d['currency'],
                    'value_eur': round(d['value_eur'], 2),
                    'pl_eur': round(pl_eur, 2),
                    'pl_pct': round(pl_pct, 2),
                }
        elif view == 'watchlist':
            for aid in updated_asset_ids:
                a = asset_by_id.get(aid)
                if not a:
                    continue
                updates[str(aid)] = {
                    'price_local': float(a.current_price) if a.current_price is not None else None,
                    'currency': a.currency or 'EUR',
                }
        elif view == 'crypto':
            # Reutilizar métricas (ya calculan value/pl) y filtrar por asset_id actualizado
            from app.services.crypto_metrics import compute_crypto_metrics
            m = compute_crypto_metrics(current_user.id)
            for p in (m.get('posiciones') or []):
                aid = p.get('asset_id')
                if aid in set(updated_asset_ids):
                    updates[str(aid)] = {
                        'price_eur': p.get('price'),
                        'value_eur': round(float(p.get('value') or 0), 2),
                        'pl_eur': round(float(p.get('pl') or 0), 2),
                        'pl_pct': round(float(p.get('pl_pct') or 0), 2),
                    }
        elif view == 'metales':
            from app.services.metales_metrics import compute_metales_metrics
            m = compute_metales_metrics(current_user.id)
            for p in (m.get('posiciones') or []):
                aid = p.get('asset_id')
                if aid in set(updated_asset_ids):
                    # Table muestra €/oz: price es EUR/g
                    price_eur_g = float(p.get('price') or 0)
                    updates[str(aid)] = {
                        'price_eur_oz': round(price_eur_g * 31.1035, 2) if price_eur_g else None,
                        'value_eur': round(float(p.get('value') or 0), 2),
                        'pl_eur': round(float(p.get('pl') or 0), 2),
                        'pl_pct': round(float(p.get('pl_pct') or 0), 2),
                    }
    return jsonify({
        'updated_asset_ids': updated_asset_ids,
        'server_now': server_now,
        'updates': updates,
    }), 200


@main_bp.route('/dashboard/state')
@login_required
def dashboard_state():
    """
    Snapshot del dashboard para polling (~30s).
    Recalcula solo NOW (patrimonio actual, último punto, widgets) sobre el HIST
    cacheado — no reconstruye la serie histórica completa.
    Incluye updated_asset_ids si el cliente envía ?since= (ISO timestamp).
    """
    from datetime import timedelta
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    from app.models.dashboard_summary_cache import DashboardSummaryCache

    c = DashboardSummaryCache.query.filter_by(user_id=current_user.id).first()
    if not c or not c.is_valid:
        return jsonify({'has_cache': False}), 200

    updated = DashboardSummaryCacheService.recompute_current_from_cache(current_user.id)
    if updated is None:
        return jsonify({'has_cache': False}), 200

    cache = DashboardSummaryCacheService.get(current_user.id)
    if cache is None:
        return jsonify({'has_cache': False}), 200

    meta = (cache.get('meta') or {}).copy()
    meta['_from_cache'] = cache.get('_from_cache', False)
    meta['_cached_at'] = cache.get('_cached_at')

    # updated_asset_ids: IDs actualizados desde el último poll del cliente
    updated_asset_ids = []
    since_param = request.args.get('since')
    if since_param:
        try:
            since = datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            if since.tzinfo:
                since = since.replace(tzinfo=None)  # SQLite sin timezone
            updated_asset_ids = get_updated_asset_ids_for_user(current_user.id, since)
        except (ValueError, TypeError):
            pass
    else:
        # Sin since: últimos 2 min por defecto (primera carga)
        since = datetime.utcnow() - timedelta(minutes=2)
        updated_asset_ids = get_updated_asset_ids_for_user(current_user.id, since)

    return jsonify({
        'has_cache': True,
        'meta': meta,
        'summary': cache,
        'updated_asset_ids': updated_asset_ids,
    }), 200

@main_bp.route('/reconciliation/adjustment-metrics', methods=['POST'])
@login_required
def reconciliation_adjustment_metrics():
    """
    Incluir o excluir el ajuste de reconciliación de un mes en métricas / gráficos / resúmenes.
    El cálculo del ajuste no cambia; solo el agregado vía income_expense_aggregator.
    """
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    from app.services.reconciliation_service import set_adjustment_included_in_metrics

    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    include = request.form.get('include_in_metrics') == '1'
    next_url = request.form.get('next') or url_for('expenses.list')

    if not next_url.startswith('/'):
        next_url = url_for('expenses.list')

    if not year or not month or month < 1 or month > 12:
        flash('Mes o año inválidos.', 'error')
        return redirect(next_url)

    set_adjustment_included_in_metrics(current_user.id, year, month, include)
    DashboardSummaryCacheService.invalidate(current_user.id)

    if include:
        flash(
            'Este ajuste volverá a contarse en medias, totales y gráficos de ingresos/gastos.',
            'success',
        )
    else:
        flash(
            'Ajuste excluido de estadísticas. El importe sigue mostrándose en la lista (solo informativo).',
            'info',
        )
    return redirect(next_url)


@main_bp.route('/reconciliation/integrate-adjustment', methods=['POST'])
@login_required
def reconciliation_integrate_adjustment():
    """
    Crea un gasto o ingreso real que absorbe el ajuste de reconciliación del mes,
    de modo que el ajuste sintético pasa a cero.
    """
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    from app.services.reconciliation_service import (
        integrate_reconciliation_adjustment_as_expense,
        integrate_reconciliation_adjustment_as_income,
    )

    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    category_id = request.form.get('category_id', type=int)
    side = (request.form.get('side') or '').strip().lower()
    next_url = request.form.get('next') or url_for('expenses.list')

    if not next_url.startswith('/'):
        next_url = url_for('expenses.list')

    if not year or not month or month < 1 or month > 12:
        flash('Mes o año inválidos.', 'error')
        return redirect(next_url)

    if not category_id:
        flash('Selecciona una categoría.', 'error')
        return redirect(next_url)

    if side == 'expense':
        obj, err, merged, applied = integrate_reconciliation_adjustment_as_expense(
            current_user.id, year, month, category_id
        )
        if err:
            flash(err, 'error')
            return redirect(next_url)
        DashboardSummaryCacheService.touch_for_dates(current_user.id, dates=[obj.date])
    elif side == 'income':
        obj, err, merged, applied = integrate_reconciliation_adjustment_as_income(
            current_user.id, year, month, category_id
        )
        if err:
            flash(err, 'error')
            return redirect(next_url)
        DashboardSummaryCacheService.touch_for_dates(current_user.id, dates=[obj.date])
    else:
        flash('Tipo de movimiento no válido.', 'error')
        return redirect(next_url)

    DashboardSummaryCacheService.invalidate(current_user.id)
    label = 'gasto' if side == 'expense' else 'ingreso'
    if merged:
        flash(
            f'Ajuste integrado: €{applied:.2f} sumados al {label} existente de esta categoría '
            f'en el mes (serie recurrente o única línea). Nuevo total €{obj.amount:.2f}.',
            'success',
        )
    else:
        flash(
            f'Ajuste integrado: nuevo {label} de €{applied:.2f} en la categoría elegida.',
            'success',
        )
    return redirect(next_url)


@main_bp.route('/dashboard/config', methods=['POST'])
@login_required
def save_dashboard_config():
    """Guardar configuración de widgets del dashboard"""
    data = request.get_json()
    
    if not data or 'widgets' not in data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    widgets = data['widgets']
    UserDashboardConfig.save_user_config(current_user.id, widgets)
    
    return jsonify({'success': True, 'message': 'Configuración guardada'})


@main_bp.route('/dashboard/layout', methods=['GET', 'POST'])
@login_required
def dashboard_layout():
    """
    Persistencia del orden de tarjetas del Dashboard global por usuario.

    - GET: devuelve {wide:[], tail:[], normal:[]}
    - POST: recibe {wide:[], tail:[], normal:[]} y persiste posiciones
    """
    if request.method == 'GET':
        rows = (
            UserDashboardLayout.query
            .filter_by(user_id=current_user.id)
            .order_by(UserDashboardLayout.lane.asc(), UserDashboardLayout.position.asc())
            .all()
        )
        out = {'wide': [], 'tail': [], 'normal': []}
        for r in rows:
            lane = (r.lane or '').strip().lower()
            if lane not in out:
                continue
            out[lane].append(r.card_id)
        return jsonify({'success': True, 'layout': out}), 200

    data = request.get_json(silent=True) or {}
    wide = data.get('wide') or []
    tail = data.get('tail') or []
    normal = data.get('normal') or []

    def _clean_ids(items):
        ids = []
        for x in (items or []):
            if not isinstance(x, str):
                continue
            s = x.strip()
            if not s:
                continue
            # Guardar tal cual el data-card-id; evitar tamaños absurdos
            if len(s) > 80:
                s = s[:80]
            ids.append(s)
        return ids

    wide = _clean_ids(wide)
    tail = _clean_ids(tail)
    normal = _clean_ids(normal)

    # Reemplazo completo: mantiene coherencia y permite que cards desaparecidas se purguen
    UserDashboardLayout.query.filter_by(user_id=current_user.id).delete()
    pos = 0
    for i, cid in enumerate(wide):
        db.session.add(UserDashboardLayout(user_id=current_user.id, card_id=cid, lane='wide', position=i))
        pos += 1
    for i, cid in enumerate(tail):
        db.session.add(UserDashboardLayout(user_id=current_user.id, card_id=cid, lane='tail', position=i))
        pos += 1
    for i, cid in enumerate(normal):
        db.session.add(UserDashboardLayout(user_id=current_user.id, card_id=cid, lane='normal', position=i))
        pos += 1
    db.session.commit()

    return jsonify({'success': True, 'count': pos}), 200


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'app': 'FollowUp',
        'version': '9.1.0'
    }, 200
