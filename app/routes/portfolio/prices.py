"""
Rutas de actualización de precios
"""
import time
from flask import jsonify, request, current_app
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app.routes.portfolio._shared import (
    price_update_progress_cache,
    price_progress_lock,
)


def update_price_progress(session_key, data):
    """Callback para actualizar el progreso"""
    with price_progress_lock:
        if session_key in price_update_progress_cache:
            price_update_progress_cache[session_key].update(data)


@portfolio_bp.route('/prices/update', methods=['POST'])
@login_required
def update_prices():
    """Inicia actualización de precios en background"""
    from app.services.market_data.services import PriceUpdater
    from flask_wtf.csrf import validate_csrf
    import threading

    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        return jsonify({'error': 'Token CSRF inválido'}), 400

    user_id = current_user.id
    session_key = f'price_update_{user_id}'

    with price_progress_lock:
        if session_key in price_update_progress_cache:
            ex = price_update_progress_cache[session_key]
            if ex.get('status') == 'running':
                return jsonify({'error': 'Ya hay una actualización en progreso'}), 400

    with price_progress_lock:
        price_update_progress_cache[session_key] = {
            'status': 'running', 'current': 0, 'total': 0,
            'current_asset': 'Iniciando...', 'success': 0, 'failed': 0, 'skipped': 0,
            'errors': [], 'start_time': time.time()
        }

    app = current_app._get_current_object()

    def run_update():
        with app.app_context():
            try:
                # Primero reconciliar delistings (quiebra/adquisición) para cerrar posiciones
                # y evitar fallos al buscar precios de activos ya deslistados
                delisting_result = {}
                from app.services.delisting_reconciliation_service import reconcile_delistings
                try:
                    delisting_result = reconcile_delistings(user_id=user_id)
                except Exception:
                    pass  # No bloquear si falla el delisting
                updater = PriceUpdater(progress_callback=lambda d: update_price_progress(session_key, d))
                result = updater.update_asset_prices(user_id=user_id)
                if delisting_result.get('created', 0) > 0:
                    result = result or {}
                    result['delistings_created'] = delisting_result.get('created', 0)
                with price_progress_lock:
                    price_update_progress_cache[session_key].update({
                        'status': 'completed', 'result': result,
                        'success': result.get('success', 0), 'failed': result.get('failed', 0),
                        'skipped': result.get('skipped', 0), 'total': result.get('total', 0),
                        'failed_assets': result.get('failed_assets', []),
                        'skipped_assets': result.get('skipped_assets', []),
                        'end_time': time.time()
                    })
                from app.services.metrics.cache import MetricsCacheService
                MetricsCacheService.invalidate(user_id)
            except Exception as e:
                import traceback
                with price_progress_lock:
                    price_update_progress_cache[session_key].update({
                        'status': 'error', 'error': str(e),
                        'traceback': traceback.format_exc(), 'end_time': time.time()
                    })

    threading.Thread(target=run_update, daemon=True).start()
    return jsonify({'status': 'started', 'session_key': session_key})


@portfolio_bp.route('/prices/update/progress', methods=['GET'])
@login_required
def price_update_progress():
    """Consulta progreso de actualización de precios"""
    session_key = f'price_update_{current_user.id}'
    with price_progress_lock:
        p = price_update_progress_cache.get(session_key, {'status': 'not_started', 'current': 0, 'total': 0})
    return jsonify(p)
