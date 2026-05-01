"""
Rutas de asset registry, asset detail, reports y about
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_file, make_response
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app import db, csrf
from sqlalchemy import text, bindparam

from app.models import (
    BrokerAccount,
    Asset,
    PortfolioHolding,
    Transaction,
    Watchlist,
    AssetRegistry,
    AssetDelisting,
    DELISTING_TYPES,
    CompanyReport,
)

def _to_utc_dt(v) -> datetime | None:
    """Convierte valores de SQLite/SQLAlchemy (str/datetime) a datetime naive UTC."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # SQLite suele devolver "YYYY-MM-DD HH:MM:SS(.ffffff)"
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
        except Exception:
            return None
    return None


def _maybe_expire_stale_report(report: CompanyReport) -> None:
    """Si el informe lleva demasiado en pending/processing, marca failed y refresca la fila."""
    from app.services.company_report_recovery import expire_company_report_if_stale

    if expire_company_report_if_stale(report):
        db.session.refresh(report)


def _parse_audio_progress_json(raw):
    """Parsea ``audio_progress_json`` de company_reports para la API / UI."""
    if raw is None or raw == '':
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _active_queue_timestamp(report) -> datetime | None:
    """Timestamp que representa el *momento de encolado* de la tarea activa de este informe.

    - Si hay audio en cola/en curso: usa ``audio_enqueued_at`` (fallback created_at).
    - Si hay informe en cola/en curso: usa ``report_enqueued_at`` (fallback created_at).
    """
    try:
        a_st = getattr(report, "audio_status", None)
        r_st = getattr(report, "status", None)
        if a_st in ("queued", "processing"):
            return getattr(report, "audio_enqueued_at", None) or getattr(report, "created_at", None)
        if r_st in ("pending", "processing"):
            return getattr(report, "report_enqueued_at", None) or getattr(report, "created_at", None)
    except Exception:
        return None
    return None


def _maybe_expire_stale_audio_queued() -> None:
    """Limpia encolados de audio irreales (informe listo, sin WAV, demasiado tiempo en cola)."""
    try:
        from app.services.company_report_recovery import expire_stale_audio_queued_rows

        expire_stale_audio_queued_rows(getattr(current_app, 'logger', None))
    except Exception:
        current_app.logger.exception('expire_stale_audio_queued_rows')


def _maybe_expire_stale_full_delivery_tail() -> None:
    try:
        from app.services.full_deliver_continuation import expire_stale_full_delivery_tails

        expire_stale_full_delivery_tails(getattr(current_app, 'logger', None))
    except Exception:
        current_app.logger.exception('expire_stale_full_delivery_tails')


def _stale_audio_queued_cutoff_utc() -> datetime:
    from app.services.company_report_recovery import _stale_audio_queued_seconds

    return datetime.utcnow() - timedelta(seconds=_stale_audio_queued_seconds())


def _row_is_stale_audio_queued(row: dict, cutoff: datetime) -> bool:
    if row.get('audio_status') != 'queued' or row.get('status') != 'completed':
        return False
    path = (row.get('audio_path') or '').strip()
    if path:
        return False
    t = _to_utc_dt(row.get('audio_enqueued_at') or row.get('created_at'))
    if not t:
        return False
    return t < cutoff


def _row_active_queue_sort_key(row: dict, cutoff: datetime) -> datetime | None:
    """Clave de ordenación global: un informe aporta como mucho un trabajo activo (audio tiene prioridad)."""
    a_st = row.get('audio_status')
    r_st = row.get('status')
    dm = row.get('delivery_mode')
    dps = row.get('delivery_phase_status')
    if a_st in ('queued', 'processing'):
        if a_st == 'queued' and _row_is_stale_audio_queued(row, cutoff):
            pass
        else:
            return _to_utc_dt(row.get('audio_enqueued_at') or row.get('created_at'))
    if (
        r_st == 'completed'
        and dm == 'full_deliver'
        and (dps == 'processing' or dps is None)
    ):
        return _to_utc_dt(row.get('completed_at') or row.get('report_enqueued_at') or row.get('created_at'))
    if r_st in ('pending', 'processing'):
        return _to_utc_dt(row.get('report_enqueued_at') or row.get('created_at'))
    return None


def _sorted_active_queue_rows() -> list[tuple[datetime, int]]:
    """Lista (tiempo_encolado, id) ordenada; define la cola global real para el lock serial."""
    cutoff = _stale_audio_queued_cutoff_utc()
    try:
        res = db.session.execute(
            text(
                """
                SELECT id, audio_status, status, audio_path,
                       audio_enqueued_at, report_enqueued_at, created_at,
                       delivery_mode, delivery_phase_status, completed_at
                FROM company_reports
                """
            )
        )
        pairs: list[tuple[datetime, int]] = []
        for r in res.mappings():
            row = dict(r)
            k = _row_active_queue_sort_key(row, cutoff)
            if k is not None:
                pairs.append((k, int(row['id'])))
        pairs.sort(key=lambda x: (x[0], x[1]))
        return pairs
    except Exception:
        current_app.logger.exception('_sorted_active_queue_rows')
        return []


def _queue_metrics_for_report(report) -> tuple[int | None, int]:
    """(posición 1-based en cola global, total trabajos activos) o (None, total) si este informe no espera."""
    rid = int(report.id)
    pairs = _sorted_active_queue_rows()
    n = len(pairs)
    for i, (_k, qid) in enumerate(pairs):
        if qid == rid:
            return i + 1, n
    return None, n


def _queue_position_for_report_obj(report) -> int | None:
    """Posición 1-based en cola global; None si este informe no está esperando turno."""
    pos, _n = _queue_metrics_for_report(report)
    return pos


def _persist_report_stages_from_steps(engine, report_id, steps_list):
    """Persiste la lista de pasos del informe (``report_stages``)."""
    from app.services.gemini_service import new_report_stages_progress_state

    base = new_report_stages_progress_state()
    base['steps'] = steps_list
    with engine.connect() as conn:
        conn.execute(
            text('UPDATE company_reports SET audio_progress_json = :j WHERE id = :rid'),
            {'j': json.dumps(base, ensure_ascii=False), 'rid': report_id},
        )
        conn.commit()


@portfolio_bp.route('/asset-registry')
@login_required
def asset_registry():
    """
    Gestión completa de AssetRegistry - Tabla global compartida
    """
    from sqlalchemy import desc, asc
    
    # Query base
    query = AssetRegistry.query
    
    # Filtros
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            db.or_(
                AssetRegistry.isin.ilike(f'%{search}%'),
                AssetRegistry.symbol.ilike(f'%{search}%'),
                AssetRegistry.name.ilike(f'%{search}%')
            )
        )
    
    # Filtro: Solo sin enriquecer (is_enriched == False, es decir, sin symbol)
    unenriched_only = request.args.get('unenriched_only', '').strip()
    if unenriched_only:
        query = query.filter(AssetRegistry.is_enriched == False)
    
    # Ordenamiento
    current_sort_by = request.args.get('sort_by', 'created_at').strip()
    current_sort_order = request.args.get('sort_order', 'desc').strip()
    
    sort_fields = {
        'isin': AssetRegistry.isin,
        'symbol': AssetRegistry.symbol,
        'name': AssetRegistry.name,
        'currency': AssetRegistry.currency,
        'exchange': AssetRegistry.ibkr_exchange,
        'mic': AssetRegistry.mic,
        'usage_count': AssetRegistry.usage_count,
        'created_at': AssetRegistry.created_at,
        'is_enriched': AssetRegistry.is_enriched
    }
    
    if current_sort_by in sort_fields:
        order_field = sort_fields[current_sort_by]
        if current_sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())
    else:
        query = query.order_by(AssetRegistry.created_at.desc())
    
    # Ejecutar query
    registries = query.all()
    
    # Estadísticas
    total = AssetRegistry.query.count()
    enriched = AssetRegistry.query.filter_by(is_enriched=True).count()
    pending = total - enriched
    
    stats = {
        'total': total,
        'enriched': enriched,
        'pending': pending,
        'percentage': (enriched / total * 100) if total > 0 else 0
    }

    # Mapeo registry_id -> delisting para mostrar en la tabla
    reg_ids = [r.id for r in registries] if registries else []
    delistings_q = AssetDelisting.query.filter(AssetDelisting.asset_registry_id.in_(reg_ids)).all() if reg_ids else []
    delistings_by_registry = {d.asset_registry_id: d for d in delistings_q}
    # Datos serializables para JS (fecha como ISO, etc.)
    delistings_js = {}
    for rid, d in delistings_by_registry.items():
        delistings_js[str(rid)] = {
            'date': d.delisting_date.isoformat(),
            'price': d.delisting_price,
            'currency': d.delisting_currency,
            'type': d.delisting_type,
            'notes': d.notes or ''
        }

    return render_template('portfolio/asset_registry.html',
                          registries=registries,
                          stats=stats,
                          sort_by=current_sort_by,
                          sort_order=current_sort_order,
                          delistings_by_registry=delistings_by_registry,
                          delistings_js=delistings_js,
                          DELISTING_TYPES=DELISTING_TYPES)


@portfolio_bp.route('/asset-registry/<int:id>/edit', methods=['POST'])
@login_required
def asset_registry_edit(id):
    """
    Editar un registro de AssetRegistry
    """
    from app.models import AssetRegistry
    from flask_wtf.csrf import validate_csrf
    
    # Validar CSRF token manualmente
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception as e:
        flash(f'❌ Token CSRF inválido. Por favor, recarga la página e intenta de nuevo.', 'error')
        return redirect(url_for('portfolio.asset_registry'))
    
    registry = AssetRegistry.query.get_or_404(id)
    
    # Actualizar campos
    registry.symbol = request.form.get('symbol', '').strip() or None
    registry.name = request.form.get('name', '').strip()
    registry.currency = request.form.get('currency', registry.currency).strip().upper() or registry.currency
    registry.ibkr_exchange = request.form.get('exchange', '').strip() or None
    registry.mic = request.form.get('mic', '').strip() or None
    registry.yahoo_suffix = request.form.get('yahoo_suffix', '').strip() or None
    registry.asset_type = request.form.get('asset_type', 'Stock').strip()
    
    # Actualizar estado de enriquecimiento según condiciones unificadas
    # Está enriquecido si tiene symbol (MIC es opcional)
    if registry.symbol:
        # Solo marcar como MANUAL si NO está ya enriquecido con otra fuente
        # Esto preserva 'OPENFIGI' o 'YAHOO_URL' si ya fue enriquecido
        if not registry.is_enriched or not registry.enrichment_source:
            registry.mark_as_enriched('MANUAL')
    else:
        # Desmarcar como enriquecido si falta symbol
        registry.is_enriched = False
        registry.enrichment_source = None
        registry.enrichment_date = None
    
    # ✅ SINCRONIZACIÓN AUTOMÁTICA con Assets
    # Buscar todos los Assets con el mismo ISIN y sincronizarlos
    from app.services.asset_registry_service import AssetRegistryService
    service = AssetRegistryService()
    
    assets_to_sync = Asset.query.filter_by(isin=registry.isin).all()
    synced_count = 0
    
    for asset in assets_to_sync:
        service.sync_asset_from_registry(asset, registry)
        synced_count += 1
    
    db.session.commit()
    
    if synced_count > 0:
        flash(f'✅ Registro actualizado: {registry.isin} (sincronizado con {synced_count} asset{"s" if synced_count > 1 else ""})', 'success')
    else:
        flash(f'✅ Registro actualizado: {registry.isin}', 'success')
    
    return redirect(url_for('portfolio.asset_registry'))


@portfolio_bp.route('/asset-registry/<int:id>/delisting', methods=['POST'])
@login_required
def asset_registry_delisting(id):
    """Añadir o actualizar baja de cotización para un AssetRegistry"""
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.asset_registry'))

    registry = AssetRegistry.query.get_or_404(id)
    delisting_date = request.form.get('delisting_date', '').strip()
    delisting_price = request.form.get('delisting_price', '0').strip().replace(',', '.')
    delisting_currency = request.form.get('delisting_currency', 'EUR').strip().upper()
    delisting_type = request.form.get('delisting_type', 'CASH_ACQUISITION').strip()
    notes = request.form.get('delisting_notes', '').strip()

    if not delisting_date:
        flash('La fecha de baja es obligatoria', 'error')
        return redirect(url_for('portfolio.asset_registry'))

    try:
        from datetime import datetime
        dt = datetime.strptime(delisting_date, '%Y-%m-%d').date()
        price = float(delisting_price) if delisting_price else 0.0
    except ValueError:
        flash('Fecha o precio inválidos', 'error')
        return redirect(url_for('portfolio.asset_registry'))

    if delisting_type not in DELISTING_TYPES:
        delisting_type = 'CASH_ACQUISITION'

    existing = AssetDelisting.query.filter_by(asset_registry_id=id).first()
    if existing:
        existing.delisting_date = dt
        existing.delisting_price = price
        existing.delisting_currency = delisting_currency
        existing.delisting_type = delisting_type
        existing.notes = notes or None
        flash(f'Baja de cotización actualizada: {registry.symbol or registry.isin} - {dt}', 'success')
    else:
        d = AssetDelisting(
            asset_registry_id=id,
            delisting_date=dt,
            delisting_price=price,
            delisting_currency=delisting_currency,
            delisting_type=delisting_type,
            notes=notes or None
        )
        db.session.add(d)
        flash(f'Baja de cotización añadida: {registry.symbol or registry.isin} - {dt}', 'success')
    db.session.commit()
    return redirect(url_for('portfolio.asset_registry'))


@portfolio_bp.route('/asset-registry/<int:id>/delisting/delete', methods=['POST'])
@login_required
def asset_registry_delisting_delete(id):
    """Eliminar baja de cotización"""
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.asset_registry'))

    d = AssetDelisting.query.filter_by(asset_registry_id=id).first()
    if d:
        db.session.delete(d)
        db.session.commit()
        flash('Baja de cotización eliminada', 'info')
    return redirect(url_for('portfolio.asset_registry'))


@portfolio_bp.route('/asset-registry/reconcile-delistings', methods=['POST'])
@login_required
def asset_registry_reconcile_delistings():
    """Ejecutar reconciliación de delistings: generar SELL para posiciones en activos delisted"""
    from flask_wtf.csrf import validate_csrf
    from app.services.delisting_reconciliation_service import reconcile_delistings
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.asset_registry'))

    try:
        result = reconcile_delistings(user_id=current_user.id)
        msg = f"Reconciliación completada: {result['created']} ventas generadas"
        if result['skipped'] > 0:
            msg += f", {result['skipped']} omitidos (ya tenían venta)"
        if result['errors']:
            msg += f". Errores: {len(result['errors'])}"
        flash(msg, 'success' if result['created'] > 0 or result['skipped'] > 0 else 'info')
        for err in result['errors'][:3]:
            flash(err, 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error en reconciliación: {str(e)}', 'error')
    return redirect(url_for('portfolio.asset_registry'))


@portfolio_bp.route('/asset-registry/<int:id>/delete', methods=['POST'])
@login_required
def asset_registry_delete(id):
    """
    Eliminar un registro de AssetRegistry
    """
    from app.models import AssetRegistry
    
    registry = AssetRegistry.query.get_or_404(id)
    isin = registry.isin
    
    db.session.delete(registry)
    db.session.commit()
    
    flash(f'🗑️ Registro eliminado: {isin}', 'info')
    return redirect(url_for('portfolio.asset_registry'))


@portfolio_bp.route('/asset-registry/<int:id>/enrich', methods=['POST'])
@login_required
def asset_registry_enrich(id):
    """
    Enriquecer un registro de AssetRegistry con OpenFIGI
    Retorna JSON con los datos actualizados
    """
    from app.models import AssetRegistry
    from app.services.asset_registry_service import AssetRegistryService
    
    registry = AssetRegistry.query.get_or_404(id)
    
    if not registry.isin:
        return jsonify({'success': False, 'error': 'Registro sin ISIN'}), 400
    
    service = AssetRegistryService()
    
    try:
        # Enriquecer con OpenFIGI
        success, message = service.enrich_from_openfigi(registry, update_db=True)
        
        if not success:
            return jsonify({'success': False, 'error': message}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Asset enriquecido correctamente',
            'data': {
                'symbol': registry.symbol,
                'name': registry.name,
                'exchange': registry.ibkr_exchange,
                'mic': registry.mic,
                'yahoo_suffix': registry.yahoo_suffix,
                'asset_type': registry.asset_type,
                'yahoo_ticker': f"{registry.symbol}{registry.yahoo_suffix or ''}" if registry.symbol else ''
            }
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/enrich-manual', methods=['POST'])
@login_required
def asset_enrich_manual(id):
    """
    Enriquecer asset manualmente (OpenFIGI o Yahoo URL)
    """
    from app.services.asset_registry_service import AssetRegistryService
    from app.models import AssetRegistry
    
    asset = Asset.query.get_or_404(id)
    
    if not asset.isin:
        return jsonify({'success': False, 'error': 'Asset sin ISIN'}), 400
    
    # Obtener registro
    registry = AssetRegistry.query.filter_by(isin=asset.isin).first()
    if not registry:
        return jsonify({'success': False, 'error': 'Asset no encontrado en registro global'}), 404
    
    service = AssetRegistryService()
    method = request.form.get('method', 'openfigi')  # 'openfigi' o 'yahoo'
    
    try:
        if method == 'yahoo':
            yahoo_url = request.form.get('yahoo_url', '').strip()
            if not yahoo_url:
                return jsonify({'success': False, 'error': 'URL no proporcionada'}), 400
            
            success, message = service.enrich_from_yahoo_url(registry, yahoo_url, update_db=True)
        else:
            # OpenFIGI
            success, message = service.enrich_from_openfigi(registry, update_db=True)
        
        if not success:
            return jsonify({'success': False, 'error': message}), 400
        
        # Sincronizar Asset local con AssetRegistry
        service.sync_asset_from_registry(asset, registry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'symbol': asset.symbol,
            'exchange': asset.exchange,
            'mic': asset.mic,
            'yahoo_suffix': asset.yahoo_suffix,
            'yahoo_ticker': asset.yahoo_ticker
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/fix-yahoo', methods=['POST'])
@login_required
def asset_fix_yahoo(id):
    """Corregir datos de asset usando URL de Yahoo Finance (legacy - ahora usa enrich-manual)"""
    from app.services.asset_registry_service import AssetRegistryService
    from app.models import AssetRegistry
    
    asset = Asset.query.get_or_404(id)
    yahoo_url = request.form.get('yahoo_url', '').strip()
    
    if not yahoo_url:
        return jsonify({'success': False, 'error': 'URL no proporcionada'}), 400
    
    try:
        # Buscar registro
        if not asset.isin:
            return jsonify({'success': False, 'error': 'Asset sin ISIN'}), 400
        
        registry = AssetRegistry.query.filter_by(isin=asset.isin).first()
        if not registry:
            return jsonify({'success': False, 'error': 'Registro no encontrado'}), 404
        
        service = AssetRegistryService()
        success, message = service.enrich_from_yahoo_url(registry, yahoo_url, update_db=True)
        
        if not success:
            return jsonify({'success': False, 'error': message}), 400
        
        # Sincronizar Asset local
        service.sync_asset_from_registry(asset, registry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'symbol': asset.symbol,
            'yahoo_suffix': asset.yahoo_suffix,
            'yahoo_ticker': asset.yahoo_ticker
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/fix-with-yahoo-url', methods=['POST'])
@login_required
def asset_fix_with_yahoo_url(id):
    """
    Corregir asset con URL de Yahoo: enriquecer registro, sincronizar asset y verificar contra Yahoo.
    Usado por el flujo "Arreglar errores" del modal de actualización y por el "!" en tablas.
    Acepta JSON o form: yahoo_url
    """
    from app.services.asset_registry_service import AssetRegistryService
    from app.models import AssetRegistry

    asset = Asset.query.get_or_404(id)
    if request.is_json:
        data = request.get_json() or {}
        yahoo_url = (data.get('yahoo_url') or '').strip()
    else:
        yahoo_url = (request.form.get('yahoo_url') or '').strip()

    if not yahoo_url:
        return jsonify({'success': False, 'error': 'URL no proporcionada'}), 400

    if not asset.isin:
        return jsonify({'success': False, 'error': 'Asset sin ISIN'}), 400

    registry = AssetRegistry.query.filter_by(isin=asset.isin).first()
    if not registry:
        return jsonify({'success': False, 'error': 'Registro no encontrado'}), 404

    try:
        service = AssetRegistryService()
        success, message, verified = service.fix_asset_with_yahoo_url(registry, yahoo_url, asset=asset)
        if not success:
            return jsonify({'success': False, 'error': message}), 400
        return jsonify({
            'success': True,
            'message': message,
            'verified': verified,
            'symbol': asset.symbol,
            'yahoo_suffix': asset.yahoo_suffix,
            'yahoo_ticker': asset.yahoo_ticker,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/update-price', methods=['POST'])
@login_required
def asset_update_price(id):
    """
    Actualiza el precio de un solo asset (tras corregir ticker con Yahoo).
    Usado por el modal de fix Yahoo cuando la comprobación es exitosa.
    """
    from app.services.market_data.services import PriceUpdater
    from flask_wtf.csrf import validate_csrf

    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        return jsonify({'success': False, 'error': 'Token CSRF inválido'}), 400

    asset = Asset.query.get_or_404(id)
    try:
        updater = PriceUpdater()
        result = updater.update_asset_prices(asset_ids=[id])
        success_count = result.get('success', 0)
        db.session.refresh(asset)
        return jsonify({
            'success': success_count > 0,
            'updated': success_count,
            'current_price': float(asset.current_price) if asset.current_price is not None else None,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/delisting', methods=['POST'])
@login_required
def asset_delisting_by_asset_id(id):
    """
    Registrar baja de cotización por asset_id (desde el modal de corrección de errores).
    Crea/actualiza el delisting en el registry del asset, ejecuta reconciliación y genera la venta.
    Acepta JSON o form: delisting_date (YYYY-MM-DD), delisting_price, delisting_currency, delisting_type, delisting_notes.
    Siempre devuelve JSON para que el modal no reciba HTML en errores.
    """
    from flask_wtf.csrf import validate_csrf
    from app.services.delisting_reconciliation_service import reconcile_delistings
    from datetime import datetime as dt_parse

    try:
        validate_csrf(request.form.get('csrf_token') or (request.get_json(silent=True) or {}).get('csrf_token'))
    except Exception:
        return jsonify({'success': False, 'error': 'Token CSRF inválido'}), 400

    try:
        asset = Asset.query.get(id)
        if not asset:
            return jsonify({'success': False, 'error': 'Activo no encontrado'}), 404
        if not asset.isin:
            return jsonify({'success': False, 'error': 'El activo no tiene ISIN'}), 400

        registry = AssetRegistry.query.filter_by(isin=asset.isin).first()
        if not registry:
            return jsonify({'success': False, 'error': 'No se encontró registro en asset-registry para este ISIN'}), 404

        if request.is_json:
            data = request.get_json(silent=True) or {}
            delisting_date = (data.get('delisting_date') or '').strip()
            delisting_price = str(data.get('delisting_price', 0)).strip().replace(',', '.')
            delisting_currency = (data.get('delisting_currency') or asset.currency or 'EUR').strip().upper()[:3]
            delisting_type = (data.get('delisting_type') or 'CASH_ACQUISITION').strip()
            notes = (data.get('delisting_notes') or '').strip()
        else:
            delisting_date = (request.form.get('delisting_date') or '').strip()
            delisting_price = (request.form.get('delisting_price') or '0').strip().replace(',', '.')
            delisting_currency = (request.form.get('delisting_currency') or asset.currency or 'EUR').strip().upper()[:3]
            delisting_type = (request.form.get('delisting_type') or 'CASH_ACQUISITION').strip()
            notes = (request.form.get('delisting_notes') or '').strip()

        if not delisting_date:
            return jsonify({'success': False, 'error': 'La fecha de baja es obligatoria'}), 400

        try:
            dt = dt_parse.strptime(delisting_date, '%Y-%m-%d').date()
            price = float(delisting_price) if delisting_price else 0.0
        except ValueError:
            return jsonify({'success': False, 'error': 'Fecha o precio inválidos (use fecha AAAA-MM-DD)'}), 400

        if delisting_type not in DELISTING_TYPES:
            delisting_type = 'CASH_ACQUISITION'

        existing = AssetDelisting.query.filter_by(asset_registry_id=registry.id).first()
        if existing:
            existing.delisting_date = dt
            existing.delisting_price = price
            existing.delisting_currency = delisting_currency
            existing.delisting_type = delisting_type
            existing.notes = notes or None
        else:
            d = AssetDelisting(
                asset_registry_id=registry.id,
                delisting_date=dt,
                delisting_price=price,
                delisting_currency=delisting_currency,
                delisting_type=delisting_type,
                notes=notes or None
            )
            db.session.add(d)
        db.session.commit()

        try:
            result = reconcile_delistings(user_id=current_user.id)
            return jsonify({
                'success': True,
                'delisting_saved': True,
                'sells_created': result.get('created', 0),
            })
        except Exception as e:
            return jsonify({
                'success': True,
                'delisting_saved': True,
                'sells_created': 0,
                'warning': 'Baja guardada pero error al generar venta: ' + str(e),
            }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Error al guardar: ' + str(e)}), 500


@portfolio_bp.route('/api/assets/search', methods=['GET'])
@login_required
def api_search_assets():
    """API: Buscar assets en AssetRegistry y Assets del usuario para autocompletado en BUY"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'success': True, 'results': []})
    
    try:
        from app.models.asset_registry import AssetRegistry
        
        # Buscar por symbol, ISIN, o nombre en AssetRegistry
        registry_results = AssetRegistry.query.filter(
            db.or_(
                AssetRegistry.symbol.ilike(f'%{query}%'),
                AssetRegistry.isin.ilike(f'%{query}%'),
                AssetRegistry.name.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        assets = []
        seen_isins = set()
        
        for r in registry_results:
            # Intentar obtener currency de un Asset existente con el mismo ISIN
            existing_asset = Asset.query.filter_by(isin=r.isin).first() if r.isin else None
            currency = existing_asset.currency if existing_asset else 'USD'  # USD por defecto
            
            assets.append({
                'id': r.id,
                'symbol': r.symbol,
                'name': r.name or r.symbol,
                'isin': r.isin,
                'currency': currency,
                'exchange': r.ibkr_exchange,
                'mic': r.mic,
                'yahoo_suffix': r.yahoo_suffix,
                'asset_type': r.asset_type or 'Stock'
            })
            seen_isins.add(r.isin)
        
        return jsonify({'success': True, 'results': assets})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Cache invalidate moved to app.routes.portfolio.dashboard

# Import routes moved to app.routes.portfolio.import_routes

# Mappings routes moved to app.routes.portfolio.mappings

# ==================== ASSET DETAILS (Sprint 3 Final) ====================

@portfolio_bp.route('/asset/<int:id>')
@login_required
def asset_detail(id):
    """
    Vista detallada de un asset con todas las métricas de Yahoo Finance
    Permite ver assets en cartera o en watchlist
    """
    asset = Asset.query.get_or_404(id)
    
    # Verificar si el usuario tiene posiciones en este asset
    holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id,
        asset_id=id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    # Verificar si el asset está en watchlist (si no tiene holdings)
    is_in_watchlist = False
    if not holdings:
        from app.models import Watchlist
        watchlist_item = Watchlist.query.filter_by(
            user_id=current_user.id,
            asset_id=id
        ).first()
        is_in_watchlist = watchlist_item is not None
        
        if not is_in_watchlist:
            flash('❌ Este activo no está en tu cartera ni en tu watchlist', 'error')
            return redirect(url_for('portfolio.dashboard'))
    
    # Calcular totales del usuario para este asset (solo si tiene holdings)
    total_quantity = sum(h.quantity for h in holdings) if holdings else 0
    total_cost = sum(h.total_cost for h in holdings) if holdings else 0
    average_buy_price = total_cost / total_quantity if total_quantity > 0 else 0
    
    # P&L en tiempo real (solo si tiene holdings)
    current_value = None
    unrealized_pl = None
    unrealized_pl_pct = None
    
    if holdings and asset.current_price:
        current_value = total_quantity * asset.current_price
        unrealized_pl = current_value - total_cost
        unrealized_pl_pct = (unrealized_pl / total_cost * 100) if total_cost > 0 else 0
    
    # Historial de transacciones del usuario para este asset
    transactions = []
    if holdings:
        transactions = Transaction.query.filter_by(
            asset_id=id
        ).join(BrokerAccount).filter(
            BrokerAccount.user_id == current_user.id
        ).order_by(Transaction.transaction_date.desc()).limit(10).all()

    # Datos para informes Gemini
    from app.models import ReportTemplate, AssetAboutSummary
    from app.services.gemini_service import is_gemini_available
    report_templates = ReportTemplate.query.filter_by(user_id=current_user.id).order_by(ReportTemplate.title).all()
    has_valid_templates = any(t.has_valid_description() for t in report_templates)
    about_summary_obj = AssetAboutSummary.query.filter_by(user_id=current_user.id, asset_id=id).first()
    about_summary = about_summary_obj.summary if about_summary_obj else None
    gemini_available = is_gemini_available()
    
    return render_template(
        'portfolio/asset_detail.html',
        asset=asset,
        holdings=holdings,
        total_quantity=total_quantity,
        total_cost=total_cost,
        average_buy_price=average_buy_price,
        current_value=current_value,
        unrealized_pl=unrealized_pl,
        unrealized_pl_pct=unrealized_pl_pct,
        transactions=transactions,
        is_in_watchlist=is_in_watchlist,
        report_templates=report_templates,
        has_valid_templates=has_valid_templates,
        about_summary=about_summary,
        gemini_available=gemini_available,
        api_report_templates_url=url_for('portfolio.api_report_templates_list'),
    )


# ==================== GEMINI INFORMES (API) ====================

def _get_report_audio_path(report):
    """Devuelve la ruta absoluta del archivo WAV del informe si existe, o None."""
    if getattr(report, 'audio_status', None) != 'completed' or not getattr(report, 'audio_path', None):
        return None
    output_folder = current_app.config.get('OUTPUT_FOLDER') or (Path(__file__).resolve().parent.parent.parent / 'output')
    full_path = (Path(output_folder).resolve() / report.audio_path).resolve()
    if not full_path.exists() or not full_path.is_file():
        return None
    try:
        if full_path.stat().st_size < 256:
            current_app.logger.warning('WAV demasiado pequeño o vacío: %s bytes %s', full_path.stat().st_size, full_path)
            return None
    except OSError:
        return None
    return full_path


def _user_can_access_asset_reports(user_id, asset_id):
    """True si el usuario puede generar/ver informes del asset (en cartera o watchlist)"""
    holdings = PortfolioHolding.query.filter_by(
        user_id=user_id, asset_id=asset_id
    ).filter(PortfolioHolding.quantity > 0).first()
    if holdings:
        return True
    watchlist_item = Watchlist.query.filter_by(
        user_id=user_id, asset_id=asset_id
    ).first()
    return watchlist_item is not None


@portfolio_bp.route('/api/report-templates', methods=['GET'], strict_slashes=False)
@login_required
def api_report_templates_list():
    """Listar plantillas del usuario"""
    from app.models import ReportTemplate
    templates = ReportTemplate.query.filter_by(user_id=current_user.id).order_by(ReportTemplate.title).all()
    return jsonify({
        'templates': [
            {
                'id': t.id,
                'title': t.title,
                'description': t.description or '',
                'points': t.get_points_list()
            }
            for t in templates
        ]
    })


@portfolio_bp.route('/api/report-templates', methods=['POST'], strict_slashes=False)
@login_required
@csrf.exempt
def api_report_templates_create():
    """Crear plantilla de informe"""
    from app.models import ReportTemplate
    try:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        points = data.get('points') or []
        if not isinstance(points, list):
            points = [p for p in (points or '').split('\n') if p.strip()] if isinstance(points, str) else []
        if not title:
            return jsonify({'success': False, 'error': 'El título es obligatorio'}), 400
        if not description:
            return jsonify({'success': False, 'error': 'La descripción es obligatoria'}), 400

        t = ReportTemplate(
            user_id=current_user.id,
            title=title,
            description=description
        )
        t.set_points_list([str(p).strip() for p in points if str(p).strip()])
        db.session.add(t)
        db.session.commit()
        return jsonify({'success': True, 'template': {'id': t.id, 'title': t.title, 'description': t.description, 'points': t.get_points_list()}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/api/report-templates/<int:template_id>', methods=['GET'], strict_slashes=False)
@login_required
def api_report_template_get(template_id):
    """Obtener una plantilla"""
    from app.models import ReportTemplate
    t = ReportTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not t:
        return jsonify({'success': False, 'error': 'Plantilla no encontrada'}), 404
    return jsonify({'id': t.id, 'title': t.title, 'description': t.description or '', 'points': t.get_points_list()})


@portfolio_bp.route('/api/report-templates/<int:template_id>', methods=['PUT'], strict_slashes=False)
@login_required
@csrf.exempt
def api_report_template_update(template_id):
    """Actualizar plantilla"""
    from app.models import ReportTemplate
    t = ReportTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not t:
        return jsonify({'success': False, 'error': 'Plantilla no encontrada'}), 404
    try:
        data = request.get_json() or {}
        if 'title' in data:
            t.title = (data.get('title') or '').strip() or t.title
        if 'description' in data:
            t.description = (data.get('description') or '').strip()
        if 'points' in data:
            points = data['points']
            if not isinstance(points, list):
                points = [p for p in (points or '').split('\n') if p.strip()] if isinstance(points, str) else []
            t.set_points_list([str(p).strip() for p in points if str(p).strip()])
        db.session.commit()
        return jsonify({'success': True, 'template': {'id': t.id, 'title': t.title, 'description': t.description, 'points': t.get_points_list()}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/api/report-templates/<int:template_id>', methods=['DELETE'], strict_slashes=False)
@login_required
@csrf.exempt
def api_report_template_delete(template_id):
    """Eliminar plantilla"""
    from app.models import ReportTemplate
    t = ReportTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not t:
        return jsonify({'success': False, 'error': 'Plantilla no encontrada'}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({'success': True})


@portfolio_bp.route('/asset/<int:id>/reports/generate', methods=['POST'])
@login_required
@csrf.exempt
def asset_reports_generate(id):
    """Iniciar generación de informe Deep Research para un asset"""
    try:
        from app.models import ReportTemplate, CompanyReport
        from app.services.gemini_service import (
            run_deep_research_report,
            new_report_stages_progress_state,
            GeminiServiceError,
            is_gemini_available,
        )
        from flask import current_app
        import threading

        asset = Asset.query.get(id)
        if not asset:
            return jsonify({'success': False, 'error': 'Asset no encontrado'}), 404
        if not _user_can_access_asset_reports(current_user.id, id):
            return jsonify({'success': False, 'error': 'Asset no está en tu cartera ni en watchlist'}), 403

        if not is_gemini_available():
            return jsonify({'success': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

        data = request.get_json() or {}
        template_id = data.get('template_id')
        if not template_id:
            return jsonify({'success': False, 'error': 'Selecciona una plantilla'}), 400

        template = ReportTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
        if not template:
            return jsonify({'success': False, 'error': 'Plantilla no encontrada'}), 404
        if not template.has_valid_description():
            return jsonify({'success': False, 'error': 'La plantilla debe tener descripción'}), 400

        # Crear registro pendiente
        report = CompanyReport(
            user_id=current_user.id,
            asset_id=id,
            template_id=template.id,
            template_title=template.title,
            status='pending',
            report_enqueued_at=datetime.utcnow(),
        )
        db.session.add(report)
        db.session.commit()

        # Capturar valores para el hilo (no pasar objetos ORM: quedan desvinculados de la sesión)
        report_id = report.id
        user_id = current_user.id
        asset_id = id
        description = template.description
        points = template.get_points_list()

        app = current_app._get_current_object()

        def run_report_background():
            """Hilo: usa conexión raw (sin sesión ORM) para evitar 'Instance is not bound to a Session'."""
            from datetime import datetime

            from app.background_tasks_lock import background_tasks_lock

            # Serialización global: informes/audio se ejecutan de uno en uno.
            with app.app_context(), background_tasks_lock(app):
                engine = db.engine

                def _update_status(st, content_val=None, error_val=None, clear_progress=False):
                    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    with engine.connect() as conn:
                        if clear_progress and st == 'completed':
                            conn.execute(
                                text("""
                            UPDATE company_reports SET status = :st, completed_at = :now
                            , content = :content, error_msg = :error, audio_progress_json = NULL
                            WHERE id = :rid
                        """),
                                {
                                    'st': st,
                                    'now': now_str,
                                    'content': content_val,
                                    'error': error_val,
                                    'rid': report_id,
                                },
                            )
                        else:
                            conn.execute(
                                text("""
                            UPDATE company_reports SET status = :st, completed_at = :now
                            , content = :content, error_msg = :error WHERE id = :rid
                        """),
                                {
                                    'st': st,
                                    'now': now_str,
                                    'content': content_val,
                                    'error': error_val,
                                    'rid': report_id,
                                },
                            )
                        conn.commit()

                try:
                    with engine.connect() as conn:
                        # Si solo se hace WHERE status='pending', SQLite/condiciones de carrera
                        # pueden dejar rowcount=0 y el hilo sale sin tocar el informe → queda "pending" para siempre.
                        r = conn.execute(text("""
                            UPDATE company_reports SET status = 'processing' WHERE id = :rid
                        """), {'rid': report_id})
                        conn.commit()
                        if r.rowcount == 0:
                            current_app.logger.error(
                                'Deep Research: no existe company_reports id=%s al pasar a processing',
                                report_id,
                            )
                            return
                except Exception as e:
                    import traceback
                    try:
                        _update_status('failed', error_val=str(e))
                    except Exception:
                        pass
                    print(traceback.format_exc())
                    return

                try:
                    with engine.connect() as conn:
                        row = conn.execute(text(
                            "SELECT name, symbol, isin FROM assets WHERE id = :aid"
                        ), {'aid': asset_id}).fetchone()
                    if not row:
                        _update_status('failed', error_val='Asset no encontrado')
                        return
                    aname = (row[0] or 'Desconocida')
                    asym = (row[1] or '')
                    aisn = (row[2] or '')

                    def _save_interaction_id(iid: str):
                        with engine.connect() as conn:
                            conn.execute(
                                text(
                                    "UPDATE company_reports SET gemini_interaction_id = :iid "
                                    "WHERE id = :rid AND status = 'processing'"
                                ),
                                {'iid': (iid or '')[:100], 'rid': report_id},
                            )
                            conn.commit()

                    def _persist_report_stages(subs: list) -> None:
                        base = new_report_stages_progress_state()
                        base['steps'] = subs
                        with engine.connect() as conn:
                            conn.execute(
                                text(
                                    'UPDATE company_reports SET audio_progress_json = :j WHERE id = :rid'
                                ),
                                {
                                    'j': json.dumps(base, ensure_ascii=False),
                                    'rid': report_id,
                                },
                            )
                            conn.commit()

                    with engine.connect() as conn:
                        conn.execute(
                            text(
                                'UPDATE company_reports SET audio_progress_json = :j WHERE id = :rid'
                            ),
                            {
                                'j': json.dumps(new_report_stages_progress_state(), ensure_ascii=False),
                                'rid': report_id,
                            },
                        )
                        conn.commit()

                    current_app.logger.info(
                        'Deep Research worker: inicio informe solo texto report_id=%s asset_id=%s user_id=%s',
                        report_id,
                        asset_id,
                        user_id,
                    )

                    status, content = run_deep_research_report(
                        aname,
                        asym,
                        aisn,
                        description,
                        points,
                        on_interaction_created=_save_interaction_id,
                        on_report_substeps=_persist_report_stages,
                    )

                    current_app.logger.info(
                        'Deep Research worker: fin informe solo texto report_id=%s resultado=%s',
                        report_id,
                        status,
                    )

                    content_val = content if status == 'completed' else None
                    error_val = content if status == 'failed' else None

                    if status == 'completed':
                        from app.services.gemini_service import (
                            generate_report_email_summary,
                            fallback_report_summary_markdown,
                            report_substeps_after_dr_ok,
                            _get_auto_collab_loop,
                        )

                        single_shot = not _get_auto_collab_loop()
                        _persist_report_stages_from_steps(
                            engine,
                            report_id,
                            report_substeps_after_dr_ok(single_shot, 'loading'),
                        )
                        try:
                            summary_md = generate_report_email_summary(content or '')
                        except Exception:
                            summary_md = fallback_report_summary_markdown(content or '')
                        _persist_report_stages_from_steps(
                            engine,
                            report_id,
                            report_substeps_after_dr_ok(single_shot, 'ok'),
                        )
                        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                        with engine.connect() as conn:
                            conn.execute(
                                text("""
                                    UPDATE company_reports SET status = 'completed', completed_at = :now,
                                    content = :content, summary_content = :sm, error_msg = NULL,
                                    audio_progress_json = NULL
                                    WHERE id = :rid
                                """),
                                {
                                    'now': now_str,
                                    'content': content,
                                    'sm': summary_md,
                                    'rid': report_id,
                                },
                            )
                            conn.commit()
                        with engine.connect() as conn:
                            cnt = conn.execute(text(
                                "SELECT COUNT(*) FROM company_reports WHERE user_id = :uid AND asset_id = :aid"
                            ), {'uid': user_id, 'aid': asset_id}).scalar()
                            if cnt and cnt > 5:
                                lim = int(cnt) - 5
                                ids = [r[0] for r in conn.execute(text("""
                                    SELECT id FROM company_reports
                                    WHERE user_id = :uid AND asset_id = :aid
                                    ORDER BY created_at ASC LIMIT :lim
                                """), {'uid': user_id, 'aid': asset_id, 'lim': lim}).fetchall()]
                                if ids:
                                    stmt = text("DELETE FROM company_reports WHERE id IN :ids").bindparams(
                                        bindparam('ids', expanding=True)
                                    )
                                    conn.execute(stmt, {'ids': ids})
                            conn.commit()
                    else:
                        _update_status(
                            status,
                            content_val=content_val,
                            error_val=error_val,
                            clear_progress=False,
                        )

                except GeminiServiceError as e:
                    try:
                        _update_status('failed', error_val=str(e))
                    except Exception:
                        pass
                except Exception as e:
                    import traceback
                    try:
                        _update_status('failed', error_val=str(e))
                    except Exception:
                        pass
                    print(traceback.format_exc())

        # Sin cola global: cada petición usa su propio hilo; varios informes seguidos
        # pueden ejecutarse en paralelo (Gemini/GPU aplicará límites de cuenta).
        thread = threading.Thread(target=run_report_background, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'report_id': report.id,
            'message': 'Generación iniciada. El informe aparecerá cuando finalice.'
        })
    except Exception as e:
        import traceback
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/reports/generate-deliver', methods=['POST'])
@login_required
@csrf.exempt
def asset_reports_generate_and_deliver(id):
    """
    Un solo clic: genera informe Deep Research, audio TTS (es-ES) y envía informe + WAV por correo.
    Muestra progreso ampliado en ``audio_progress_json`` (``full_pipeline``): plan, validación,
    informe, guion, TTS y correo.
    """
    try:
        from app.models import ReportTemplate, CompanyReport
        from app.services.gemini_service import (
            run_deep_research_report,
            new_full_pipeline_progress_state,
            GeminiServiceError,
            is_gemini_available,
        )
        from flask import current_app
        import threading
        from datetime import datetime

        asset = Asset.query.get(id)
        if not asset:
            return jsonify({'success': False, 'error': 'Asset no encontrado'}), 404
        if not _user_can_access_asset_reports(current_user.id, id):
            return jsonify({'success': False, 'error': 'Asset no está en tu cartera ni en watchlist'}), 403

        if not is_gemini_available():
            return jsonify({'success': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

        if not current_user.email:
            return jsonify({'success': False, 'error': 'Tu cuenta no tiene email; no se puede enviar el informe'}), 400
        if not current_app.config.get('MAIL_SERVER') or not current_app.config.get('MAIL_USERNAME'):
            return jsonify({'success': False, 'error': 'El correo no está configurado en el servidor'}), 503

        data = request.get_json() or {}
        template_id = data.get('template_id')
        if not template_id:
            return jsonify({'success': False, 'error': 'Selecciona una plantilla'}), 400

        template = ReportTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
        if not template:
            return jsonify({'success': False, 'error': 'Plantilla no encontrada'}), 404
        if not template.has_valid_description():
            return jsonify({'success': False, 'error': 'La plantilla debe tener descripción'}), 400

        report = CompanyReport(
            user_id=current_user.id,
            asset_id=id,
            template_id=template.id,
            template_title=template.title,
            status='pending',
            report_enqueued_at=datetime.utcnow(),
            delivery_mode='full_deliver',
            delivery_phase_status='processing',
        )
        db.session.add(report)
        db.session.commit()

        report_id = report.id
        user_id = current_user.id
        asset_id = id
        description = template.description
        points = template.get_points_list()
        report_template_title = (template.title or f'Informe {report_id}')[:200]

        app = current_app._get_current_object()

        def run_full_deliver():
            from app.background_tasks_lock import background_tasks_lock

            # Serialización global: pipelines largos de uno en uno.
            with app.app_context(), background_tasks_lock(app):
                engine = db.engine

                def _persist(json_obj):
                    with engine.connect() as conn:
                        conn.execute(
                            text(
                                'UPDATE company_reports SET audio_progress_json = :j, audio_error_msg = NULL WHERE id = :rid'
                            ),
                            {'j': json.dumps(json_obj, ensure_ascii=False), 'rid': report_id},
                        )
                        conn.commit()

                def _update_status_fail(err: str) -> None:
                    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    with engine.connect() as conn:
                        conn.execute(
                            text(
                                """
                            UPDATE company_reports SET status = 'failed', error_msg = :e, completed_at = :now
                            WHERE id = :rid
                        """
                            ),
                            {'e': err[:8000], 'now': now_str, 'rid': report_id},
                        )
                        conn.commit()

                pstate: dict = new_full_pipeline_progress_state()
                try:
                    _persist(pstate)
                    with engine.connect() as conn:
                        r = conn.execute(
                            text('UPDATE company_reports SET status = :st WHERE id = :rid'),
                            {'st': 'processing', 'rid': report_id},
                        )
                        conn.commit()
                        if r.rowcount == 0:
                            return
                except Exception as e:
                    try:
                        pstate['steps'][0]['status'] = 'error'
                        pstate['steps'][0]['error'] = str(e)[:2000]
                        _persist(pstate)
                        _update_status_fail(str(e))
                    except Exception:
                        pass
                    return

                aname = asym = aisn = ''
                try:
                    with engine.connect() as conn:
                        row = conn.execute(
                            text('SELECT name, symbol, isin FROM assets WHERE id = :aid'),
                            {'aid': asset_id},
                        ).fetchone()
                    if not row:
                        _update_status_fail('Asset no encontrado')
                        return
                    aname = (row[0] or 'Desconocida')
                    asym = (row[1] or '')
                    aisn = (row[2] or '')

                    def _save_iid(iid: str):
                        with engine.connect() as conn:
                            conn.execute(
                                text(
                                    "UPDATE company_reports SET gemini_interaction_id = :iid "
                                    "WHERE id = :rid AND status = 'processing'"
                                ),
                                {'iid': (iid or '')[:100], 'rid': report_id},
                            )
                            conn.commit()

                    def _on_report_subs(subs: list) -> None:
                        nonlocal pstate
                        for i in range(min(len(subs), len(pstate['steps']))):
                            pstate['steps'][i] = dict(subs[i])
                        _persist(pstate)

                    current_app.logger.info(
                        'Deep Research worker: inicio pipeline informe+audio+correo report_id=%s asset_id=%s user_id=%s',
                        report_id,
                        asset_id,
                        user_id,
                    )

                    st_dr, content_dr = run_deep_research_report(
                        aname,
                        asym,
                        aisn,
                        description,
                        points,
                        on_interaction_created=_save_iid,
                        on_report_substeps=_on_report_subs,
                    )

                    current_app.logger.info(
                        'Deep Research worker: fin fase DR en pipeline report_id=%s resultado=%s',
                        report_id,
                        st_dr,
                    )

                    if st_dr != 'completed':
                        _persist(pstate)
                        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                        with engine.connect() as conn:
                            conn.execute(
                                text(
                                    'UPDATE company_reports SET status = :st, error_msg = :err, completed_at = :now WHERE id = :rid'
                                ),
                                {
                                    'st': 'failed',
                                    'err': (content_dr or '')[:8000],
                                    'now': now_str,
                                    'rid': report_id,
                                },
                            )
                            conn.commit()
                        return

                    from app.services.full_deliver_continuation import execute_full_deliver_tail

                    execute_full_deliver_tail(
                        app,
                        engine=engine,
                        report_id=report_id,
                        user_id=user_id,
                        asset_id=asset_id,
                        aname=aname,
                        report_template_title=report_template_title,
                        content_dr=content_dr or '',
                        pstate=pstate,
                    )

                except GeminiServiceError as e:
                    try:
                        pstate = new_full_pipeline_progress_state()
                        pstate['steps'][0]['status'] = 'error'
                        pstate['steps'][0]['error'] = str(e)[:4000]
                        _persist(pstate)
                        with engine.connect() as conn:
                            conn.execute(
                                text(
                                    'UPDATE company_reports SET status = :st, error_msg = :e WHERE id = :rid'
                                ),
                                {'st': 'failed', 'e': str(e)[:8000], 'rid': report_id},
                            )
                            conn.commit()
                    except Exception:
                        pass
                except Exception as e:
                    import traceback

                    current_app.logger.exception('generate-deliver: %s', e)
                    try:
                        pstate = new_full_pipeline_progress_state()
                        pstate['steps'][0]['status'] = 'error'
                        pstate['steps'][0]['error'] = str(e)[:2000]
                        _persist(pstate)
                        with engine.connect() as conn:
                            conn.execute(
                                text(
                                    'UPDATE company_reports SET status = :st, error_msg = :e WHERE id = :rid'
                                ),
                                {'st': 'failed', 'e': str(e)[:8000], 'rid': report_id},
                            )
                            conn.commit()
                    except Exception:
                        pass
                    print(traceback.format_exc())

        # Sin cola global en servidor (véase también asset_reports_generate).
        th = threading.Thread(target=run_full_deliver, daemon=True)
        th.start()

        return jsonify(
            {
                'success': True,
                'report_id': report.id,
                'message': 'Iniciado: informe, audio y envío por correo. Puedes salir; recibirás un email al terminar.',
            }
        )
    except Exception as e:
        import traceback
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/reports')
@login_required
def asset_reports_list(id):
    """Listar informes del asset (máx 5)"""
    from app.models import CompanyReport

    asset = Asset.query.get_or_404(id)
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'error': 'No autorizado'}), 403

    _maybe_expire_stale_full_delivery_tail()
    _maybe_expire_stale_audio_queued()
    pairs = _sorted_active_queue_rows()
    pos_by_id = {qid: i + 1 for i, (_k, qid) in enumerate(pairs)}

    reports = CompanyReport.query.filter_by(
        user_id=current_user.id,
        asset_id=id
    ).order_by(CompanyReport.created_at.desc()).limit(5).all()

    return jsonify({
        'queue_waiting_total': len(pairs),
        'reports': [
            {
                'id': r.id,
                'status': r.status,
                'audio_status': getattr(r, 'audio_status', None),
                'delivery_mode': getattr(r, 'delivery_mode', None),
                'delivery_phase_status': getattr(r, 'delivery_phase_status', None),
                'template_title': r.template_title or f'Informe {r.id}',
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'completed_at': r.completed_at.isoformat() if r.completed_at else None,
                'queue_position': pos_by_id.get(r.id),
            }
            for r in reports
        ],
    })


@portfolio_bp.route('/asset/<int:id>/reports/<int:report_id>')
@login_required
def asset_report_detail(id, report_id):
    """Obtener un informe concreto"""
    asset = Asset.query.get(id)
    if not asset:
        return jsonify({'error': 'Asset no encontrado'}), 404
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'error': 'No autorizado'}), 403

    report = CompanyReport.query.filter_by(
        id=report_id,
        user_id=current_user.id,
        asset_id=id
    ).first()
    if not report:
        return jsonify({'error': 'Informe no encontrado'}), 404

    _maybe_expire_stale_report(report)
    _maybe_expire_stale_full_delivery_tail()
    _maybe_expire_stale_audio_queued()
    db.session.refresh(report)

    qp_detail: int | None = None
    qwait_detail = 0
    try:
        qp_detail, qwait_detail = _queue_metrics_for_report(report)
    except Exception:
        current_app.logger.exception('queue_metrics asset_report_detail')

    sm_raw = getattr(report, 'summary_content', None)
    if sm_raw is not None and str(sm_raw).strip():
        from app.services.gemini_service import sanitize_report_summary_markdown

        summary_out = sanitize_report_summary_markdown(str(sm_raw))
    else:
        summary_out = sm_raw

    return jsonify({
        'id': report.id,
        'content': report.content,
        'summary_content': summary_out,
        'status': report.status,
        'error_msg': report.error_msg,
        'template_title': report.template_title,
        'created_at': report.created_at.isoformat() if report.created_at else None,
        'completed_at': report.completed_at.isoformat() if report.completed_at else None,
        'audio_status': getattr(report, 'audio_status', None),
        'audio_path': getattr(report, 'audio_path', None),
        'audio_error_msg': getattr(report, 'audio_error_msg', None),
        'audio_completed_at': report.audio_completed_at.isoformat() if getattr(report, 'audio_completed_at', None) else None,
        'audio_progress': _parse_audio_progress_json(getattr(report, 'audio_progress_json', None)),
        'queue_position': qp_detail,
        'queue_waiting_total': qwait_detail,
        'email_status': getattr(report, 'email_status', None),
        'email_error_msg': getattr(report, 'email_error_msg', None),
        'email_completed_at': report.email_completed_at.isoformat() if getattr(report, 'email_completed_at', None) else None,
        'delivery_mode': getattr(report, 'delivery_mode', None),
        'delivery_phase_status': getattr(report, 'delivery_phase_status', None),
    })


@portfolio_bp.route('/asset/<int:id>/reports/<int:report_id>/send-email', methods=['POST'])
@login_required
@csrf.exempt
def asset_report_send_email(id, report_id):
    """Enviar informe por correo al usuario registrado"""
    from app.utils.email import send_report_email
    from app.services.gemini_service import sanitize_report_summary_markdown

    asset = Asset.query.get(id)
    if not asset:
        return jsonify({'success': False, 'error': 'Asset no encontrado'}), 404
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    report = CompanyReport.query.filter_by(
        id=report_id,
        user_id=current_user.id,
        asset_id=id
    ).first()
    if not report:
        return jsonify({'success': False, 'error': 'Informe no encontrado'}), 404

    if report.status != 'completed':
        return jsonify({'success': False, 'error': 'Solo se pueden enviar informes completados'}), 400

    if not current_user.email:
        return jsonify({'success': False, 'error': 'No tienes correo asociado a tu cuenta'}), 400

    if not current_app.config.get('MAIL_SERVER') or not current_app.config.get('MAIL_USERNAME'):
        return jsonify({'success': False, 'error': 'El correo no está configurado en el servidor'}), 503

    try:
        audio_path_arg = None
        audio_path_obj = _get_report_audio_path(report)
        if audio_path_obj:
            audio_path_arg = str(audio_path_obj)
            current_app.logger.info('Enviando informe con audio adjunto: %s', audio_path_arg)
        else:
            current_app.logger.info('Enviando informe sin audio (no encontrado o no generado): report_id=%s, audio_status=%s, audio_path=%s',
                report_id, getattr(report, 'audio_status', None), getattr(report, 'audio_path', None))
        sm = (getattr(report, 'summary_content', None) or '').strip()
        if sm:
            email_body_md = sanitize_report_summary_markdown(sm)
        else:
            email_body_md = report.content or ''

        send_report_email(
            user=current_user,
            asset_name=asset.name or asset.symbol or asset.isin or 'Activo',
            report_title=report.template_title or f'Informe {report.id}',
            email_body_markdown=email_body_md,
            audio_file_path=audio_path_arg,
            full_report_markdown_for_pdf=report.content or '',
        )
        msg = 'Informe enviado a ' + current_user.email
        if audio_path_arg:
            msg += ' (con audio adjunto)'
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        current_app.logger.exception('Error enviando informe por correo')
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/asset/<int:id>/reports/<int:report_id>/generate-audio', methods=['POST'])
@login_required
@csrf.exempt
def asset_report_generate_audio(id, report_id):
    """Iniciar generación de audio TTS en background"""
    from app.services.gemini_service import (
        generate_report_tts_audio,
        is_gemini_available,
        new_audio_progress_steps_state,
    )
    from flask import current_app
    import threading

    asset = Asset.query.get(id)
    if not asset:
        return jsonify({'success': False, 'error': 'Asset no encontrado'}), 404
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    report = CompanyReport.query.filter_by(
        id=report_id,
        user_id=current_user.id,
        asset_id=id
    ).first()
    if not report:
        return jsonify({'success': False, 'error': 'Informe no encontrado'}), 404

    if report.status != 'completed':
        return jsonify({'success': False, 'error': 'Solo se puede generar audio de informes completados'}), 400

    if not is_gemini_available():
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

    audio_status = getattr(report, 'audio_status', None)
    if audio_status in ('processing', 'queued'):
        # Idempotente: si ya hay una generación en curso (o en cola), no fallar la UI.
        return jsonify(
            {
                'success': True,
                'message': 'Audio ya en cola/generándose. Puede tardar unos minutos.',
                'audio_ready': False,
            }
        )
    if audio_status == 'completed' and getattr(report, 'audio_path', None):
        return jsonify({'success': True, 'message': 'El audio ya existe', 'audio_ready': True})

    output_folder = current_app.config.get('OUTPUT_FOLDER') or (Path(__file__).resolve().parent.parent.parent / 'output')
    audio_dir = Path(output_folder).resolve() / 'reports_audio'
    audio_path = audio_dir / f'report_{report_id}.wav'
    report_content = report.content or ''
    app_obj = current_app._get_current_object()

    # Marcar inmediatamente en BD para que la UI refleje "en cola" aunque el hilo espere el lock.
    # (El hilo setea processing al entrar en el lock; aquí solo aseguramos visibilidad y posición.)
    try:
        conn0 = db.engine.connect()
        try:
            pj0 = {'steps': new_audio_progress_steps_state()}
            conn0.execute(
                text(
                    """
                    UPDATE company_reports
                    SET audio_status = 'queued', audio_error_msg = NULL, audio_path = NULL,
                        audio_completed_at = NULL, audio_progress_json = :j,
                        audio_enqueued_at = :now
                    WHERE id = :rid
                    """
                ),
                {
                    'rid': report_id,
                    'j': json.dumps(pj0, ensure_ascii=False),
                    'now': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                },
            )
            conn0.commit()
        finally:
            conn0.close()
    except Exception:
        # Best-effort: si falla, el hilo actualizará estado al entrar al lock.
        pass

    current_app.logger.info(
        'Audio TTS encolado: report_id=%s asset_id=%s user_id=%s',
        report_id,
        id,
        current_user.id,
    )

    def _run_tts():
        from app.background_tasks_lock import background_tasks_lock

        # Serialización global: una tarea larga a la vez (incluye regeneraciones).
        with app_obj.app_context(), background_tasks_lock(app_obj):
            from datetime import datetime

            conn = db.engine.connect()
            try:
                conn.execute(text("""
                    UPDATE company_reports SET audio_status = 'processing', audio_error_msg = NULL
                    WHERE id = :rid
                """), {'rid': report_id})
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()

            app_obj.logger.info('Audio TTS en ejecución (lock adquirido): report_id=%s', report_id)

            status = 'failed'
            error_msg = None
            final_path = f'reports_audio/report_{report_id}.wav'
            now_str = datetime.utcnow().isoformat()
            def _persist_audio_progress(pj: dict) -> None:
                c = db.engine.connect()
                try:
                    c.execute(
                        text('UPDATE company_reports SET audio_progress_json = :j WHERE id = :rid'),
                        {'j': json.dumps(pj, ensure_ascii=False), 'rid': report_id},
                    )
                    c.commit()
                except Exception:
                    c.rollback()
                finally:
                    c.close()

            try:
                generate_report_tts_audio(
                    report_content,
                    str(audio_path),
                    on_progress=_persist_audio_progress,
                )
                status = 'completed'
            except Exception as e:
                error_msg = str(e)
                final_path = None
                current_app.logger.exception('TTS falló: %s', e)

            conn2 = db.engine.connect()
            try:
                if status == 'completed':
                    conn2.execute(
                        text("""
                        UPDATE company_reports
                        SET audio_status = :st, audio_error_msg = NULL, audio_path = :path,
                            audio_completed_at = :now, audio_progress_json = NULL
                        WHERE id = :rid
                    """),
                        {
                            'st': status,
                            'path': final_path,
                            'now': now_str,
                            'rid': report_id,
                        },
                    )
                else:
                    conn2.execute(
                        text("""
                        UPDATE company_reports
                        SET audio_status = 'failed', audio_error_msg = :err, audio_path = NULL,
                            audio_completed_at = NULL
                        WHERE id = :rid
                    """),
                        {'err': error_msg, 'rid': report_id},
                    )
                conn2.commit()
            except Exception:
                conn2.rollback()
            finally:
                conn2.close()

    threading.Thread(target=_run_tts, daemon=True).start()
    return jsonify({'success': True, 'message': 'Generando audio en segundo plano. Puede tardar unos minutos.'})


@portfolio_bp.route('/asset/<int:id>/reports/<int:report_id>/reset-audio', methods=['POST'])
@login_required
@csrf.exempt
def asset_report_reset_audio(id, report_id):
    """Resetear estado de audio para permitir reintentar (cuando falló o se quedó colgado)"""
    asset = Asset.query.get(id)
    if not asset:
        return jsonify({'success': False, 'error': 'Asset no encontrado'}), 404
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    report = CompanyReport.query.filter_by(
        id=report_id,
        user_id=current_user.id,
        asset_id=id
    ).first()
    if not report:
        return jsonify({'success': False, 'error': 'Informe no encontrado'}), 404

    if report.status != 'completed':
        return jsonify({'success': False, 'error': 'Solo se puede resetear audio de informes completados'}), 400

    conn = db.engine.connect()
    try:
        conn.execute(
            text("""
            UPDATE company_reports
            SET audio_status = NULL, audio_path = NULL, audio_error_msg = NULL,
                audio_completed_at = NULL, audio_progress_json = NULL
            WHERE id = :rid
        """),
            {'rid': report_id},
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

    current_app.logger.info(
        'Informe audio reseteado (reintentar): report_id=%s asset_id=%s user_id=%s',
        report_id,
        id,
        current_user.id,
    )
    return jsonify({'success': True, 'message': 'Audio reseteado. Puedes generar de nuevo.'})


@portfolio_bp.route('/asset/<int:id>/reports/<int:report_id>/audio')
@login_required
def asset_report_audio(id, report_id):
    """Descargar o reproducir el audio TTS del informe.
    No usar first_or_404: el <audio> del navegador no debe recibir HTML de error (provoca 0:00 y play desactivado)."""
    from flask import send_file

    def _plain(msg: str, code: int):
        r = make_response(msg, code)
        r.mimetype = 'text/plain; charset=utf-8'
        return r

    asset = Asset.query.get(id)
    if not asset:
        return _plain('Not found', 404)
    if not _user_can_access_asset_reports(current_user.id, id):
        return _plain('Forbidden', 403)

    report = CompanyReport.query.filter_by(
        id=report_id,
        user_id=current_user.id,
        asset_id=id
    ).first()
    if not report:
        return _plain('Not found', 404)

    full_path = _get_report_audio_path(report)
    if not full_path:
        return _plain('Audio not available or file missing', 404)

    # download=1 en query → forzar descarga; sin param → permitir reproducción en navegador
    force_download = request.args.get('download') == '1'
    download_name = f'informe_{report.template_title or report_id}_{asset.name or asset.symbol or "report"}.wav'.replace(' ', '_')
    return send_file(
        str(full_path),
        mimetype='audio/wav',
        as_attachment=force_download,
        download_name=download_name
    )


@portfolio_bp.route('/api/reports/<int:report_id>/status')
@login_required
def api_report_status(report_id):
    """Estado de un informe (para poll desde frontend)"""
    report = CompanyReport.query.filter_by(
        id=report_id,
        user_id=current_user.id
    ).first()
    if not report:
        return jsonify({'error': 'Informe no encontrado'}), 404

    _maybe_expire_stale_report(report)
    _maybe_expire_stale_audio_queued()
    db.session.refresh(report)

    queue_position: int | None = None
    queue_waiting_total = 0
    try:
        queue_position, queue_waiting_total = _queue_metrics_for_report(report)
    except Exception:
        current_app.logger.exception('queue_metrics api_report_status')

    return jsonify({
        'id': report.id,
        'status': report.status,
        'error_msg': report.error_msg,
        'completed_at': report.completed_at.isoformat() if report.completed_at else None,
        'audio_status': getattr(report, 'audio_status', None),
        'audio_path': getattr(report, 'audio_path', None),
        'audio_error_msg': getattr(report, 'audio_error_msg', None),
        'audio_progress': _parse_audio_progress_json(getattr(report, 'audio_progress_json', None)),
        'queue_position': queue_position,
        'queue_waiting_total': queue_waiting_total,
        'email_status': getattr(report, 'email_status', None),
        'email_error_msg': getattr(report, 'email_error_msg', None),
    })


@portfolio_bp.route('/asset/<int:id>/about/generate', methods=['POST'])
@login_required
@csrf.exempt
def asset_about_generate(id):
    """Generar resumen About the Company (llamada rápida, síncrona)"""
    from app.models import AssetAboutSummary
    from app.services.gemini_service import generate_about_summary, GeminiServiceError, is_gemini_available

    asset = Asset.query.get_or_404(id)
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'success': False, 'error': 'Asset no está en tu cartera ni en watchlist'}), 403

    if not is_gemini_available():
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

    try:
        summary_text = generate_about_summary(asset)
    except GeminiServiceError as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    # Guardar o actualizar
    about = AssetAboutSummary.query.filter_by(
        user_id=current_user.id,
        asset_id=id
    ).first()
    if not about:
        about = AssetAboutSummary(user_id=current_user.id, asset_id=id)
        db.session.add(about)
    about.summary = summary_text
    db.session.commit()

    return jsonify({
        'success': True,
        'summary': summary_text
    })


@portfolio_bp.route('/asset/<int:id>/about')
@login_required
def asset_about_get(id):
    """Obtener resumen About the Company guardado"""
    from app.models import AssetAboutSummary

    asset = Asset.query.get_or_404(id)
    if not _user_can_access_asset_reports(current_user.id, id):
        return jsonify({'error': 'No autorizado'}), 403

    about = AssetAboutSummary.query.filter_by(
        user_id=current_user.id,
        asset_id=id
    ).first()

    return jsonify({
        'summary': about.summary if about else None
    })



# Prices, performance, api/evolution, api/benchmarks moved to portfolio package


# ============================================================================
# WATCHLIST ROUTES - Sprint 6 HITO 2
# ============================================================================