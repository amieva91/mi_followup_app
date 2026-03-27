"""
Rutas de importación CSV
"""
import os
import time
import traceback
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.routes import portfolio_bp
from app.routes.portfolio._shared import (
    get_import_progress,
    set_import_progress,
    allowed_file,
    get_or_create_broker_account,
    UPLOAD_FOLDER,
)
from app import db
from app.services.csv_detector import detect_and_parse
from app.services.importer_v2 import CSVImporterV2


@portfolio_bp.route('/import')
@login_required
def import_csv():
    """Formulario para subir CSV con auto-detección de broker"""
    return render_template('portfolio/import_csv.html', title='Importar CSV')


@portfolio_bp.route('/import/progress')
@login_required
def import_progress():
    """Endpoint para consultar progreso de importación en tiempo real.
    Usa archivo compartido para que funcione con varios workers de Gunicorn."""
    progress = get_import_progress(current_user.id)

    if not progress:
        return jsonify({
            'status': 'idle',
            'message': 'No hay importación en curso'
        })

    # Si es fase de completado, devolver stats detalladas
    if progress.get('phase') == 'completed':
        stats = progress.get('stats', {})
        return jsonify({
            'status': 'completed',
            'stats': {
                'transactions_created': stats.get('transactions_created', 0),
                'transactions_skipped': stats.get('transactions_skipped', 0),
                'holdings_created': stats.get('holdings_created', 0),
                'dividends_created': stats.get('dividends_created', 0),
                'fees_created': stats.get('fees_created', 0),
                'deposits_created': stats.get('deposits_created', 0),
                'withdrawals_created': stats.get('withdrawals_created', 0),
                'enrichment_success': stats.get('enrichment_success', 0),
                'enrichment_needed': stats.get('enrichment_needed', 0),
            }
        })

    # Si es fase de archivo completado (transición entre archivos)
    if progress.get('phase') == 'file_completed':
        return jsonify({
            'status': 'file_completed',
            'message': progress.get('message', ''),
            'current_file': progress.get('current_file'),
            'file_number': progress.get('file_number'),
            'total_files': progress.get('total_files'),
            'completed_files': progress.get('completed_files', []),
            'pending_files': progress.get('pending_files', [])
        })

    # Fase de enriquecimiento/procesamiento
    return jsonify({
        'status': 'processing',
        'current': progress.get('current', 0),
        'total': progress.get('total', 0),
        'message': progress.get('message', ''),
        'percentage': progress.get('percentage', 0),
        'current_file': progress.get('current_file'),
        'file_number': progress.get('file_number'),
        'total_files': progress.get('total_files'),
        'completed_files': progress.get('completed_files', []),
        'pending_files': progress.get('pending_files', [])
    })


@portfolio_bp.route('/import/process', methods=['POST'])
@login_required
def import_csv_process():
    """Procesa uno o múltiples archivos CSV subidos con auto-detección de broker"""
    from app.services.import_debug_logger import setup_import_debug_logger
    debug_log = setup_import_debug_logger()
    debug_log.info(f"Usuario {current_user.id} | Archivos recibidos: {list(request.files.keys())}")

    if 'csv_files' not in request.files:
        debug_log.warning("Abort: csv_files no en request")
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))

    files = request.files.getlist('csv_files')
    debug_log.info(f"Lista de archivos: {[f.filename for f in files]}")

    if not files or len(files) == 0 or files[0].filename == '':
        debug_log.warning("Abort: lista de archivos vacía")
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))

    for file in files:
        if not allowed_file(file.filename):
            debug_log.warning(f"Abort: archivo no válido {file.filename}")
            flash(f'❌ Archivo no válido: {file.filename} (solo se permiten archivos CSV)', 'error')
            return redirect(url_for('portfolio.import_csv'))

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    total_stats = {
        'files_processed': 0,
        'files_failed': 0,
        'transactions_created': 0,
        'transactions_skipped': 0,
        'holdings_created': 0,
        'dividends_created': 0,
        'assets_created': 0,
        'fees_created': 0,
        'deposits_created': 0,
        'withdrawals_created': 0,
        'deposits_skipped': [],
    }

    failed_files = []
    completed_files = []
    total_files = len(files)
    failed_enrichment_cache = set()  # ISINs cuyo enriquecimiento falló (evita reintentos entre archivos)

    # En cuanto el cuerpo POST está completo (esta vista ya corre): el polling puede leer esto.
    # Evita pantalla 0% mientras el primer archivo se guarda y se parsea (muy largo en prod).
    set_import_progress(current_user.id, {
        'current': 0,
        'total': 1,
        'message': 'Preparando importación…',
        'percentage': 0,
        'current_file': None,
        'file_number': 0,
        'total_files': total_files,
        'completed_files': [],
        'pending_files': [secure_filename(f.filename) for f in files],
    })

    for file_idx, file in enumerate(files):
        filepath = None
        try:
            file_number = file_idx + 1
            filename = secure_filename(file.filename)
            debug_log.info(f"--- Archivo {file_number}/{total_files}: {filename} ---")

            filepath = os.path.join(UPLOAD_FOLDER, f"temp_{current_user.id}_{filename}")
            file.save(filepath)
            debug_log.debug(f"Archivo guardado en {filepath}")

            remaining = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
            set_import_progress(current_user.id, {
                'current': 0,
                'total': 1,
                'message': f'Analizando {filename}…',
                'percentage': 0,
                'current_file': filename,
                'file_number': file_number,
                'total_files': total_files,
                'completed_files': completed_files.copy(),
                'pending_files': remaining.copy(),
            })

            parsed_data = detect_and_parse(filepath)
            broker_format = parsed_data.get('format', 'unknown')
            debug_log.info(f"Formato detectado: {broker_format}")
            debug_log.debug(f"Claves en parsed_data: {list(parsed_data.keys())}")
            for k in ['trades', 'dividends', 'deposits', 'withdrawals', 'fees', 'holdings']:
                cnt = len(parsed_data.get(k, []))
                if cnt > 0:
                    debug_log.info(f"  {k}: {cnt} registros")

            account = get_or_create_broker_account(current_user.id, broker_format)
            debug_log.info(f"Cuenta broker: id={account.id}")

            importer = CSVImporterV2(
                user_id=current_user.id,
                broker_account_id=account.id,
                enable_enrichment=True,
                failed_enrichment_cache=failed_enrichment_cache
            )

            # Estado inicial para que el polling muestre progreso desde el primer archivo
            remaining = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
            set_import_progress(current_user.id, {
                'current': 0,
                'total': 1,
                'message': f'Procesando {filename}...',
                'percentage': 0,
                'current_file': filename,
                'file_number': file_number,
                'total_files': total_files,
                'completed_files': completed_files.copy(),
                'pending_files': remaining.copy()
            })

            def progress_callback(current, total, message):
                remaining = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
                set_import_progress(current_user.id, {
                    'current': current,
                    'total': total,
                    'message': message,
                    'percentage': int((current / total) * 100) if total > 0 else 0,
                    'current_file': filename,
                    'file_number': file_number,
                    'total_files': total_files,
                    'completed_files': completed_files.copy(),
                    'pending_files': remaining.copy()
                })

            stats = importer.import_data(parsed_data, progress_callback=progress_callback)

            debug_log.info(f"Stats archivo {filename}: {stats}")
            completed_files.append(filename)

            remaining = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
            set_import_progress(current_user.id, {
                'phase': 'file_completed',
                'current_file': filename,
                'file_number': file_number,
                'total_files': total_files,
                'completed_files': completed_files.copy(),
                'pending_files': remaining,
                'message': f'✅ {filename} importado correctamente'
            })

            time.sleep(0.3)

            total_stats['files_processed'] += 1
            total_stats['transactions_created'] += stats['transactions_created']
            total_stats['holdings_created'] += stats['holdings_created']
            total_stats['dividends_created'] += stats['dividends_created']
            total_stats['assets_created'] += stats['assets_created']
            total_stats['fees_created'] += stats.get('fees_created', 0)
            total_stats['deposits_created'] += stats.get('deposits_created', 0)
            total_stats['withdrawals_created'] += stats.get('withdrawals_created', 0)
            total_stats['deposits_skipped'].extend(stats.get('deposits_skipped', []))

            if 'enrichment_needed' not in total_stats:
                total_stats['enrichment_needed'] = 0
                total_stats['enrichment_success'] = 0
                total_stats['enrichment_failed'] = 0

            total_stats['enrichment_needed'] += stats.get('enrichment_needed', 0)
            total_stats['enrichment_success'] += stats.get('enrichment_success', 0)
            total_stats['enrichment_failed'] += stats.get('enrichment_failed', 0)

            if os.path.exists(filepath):
                os.remove(filepath)

        except Exception as e:
            db.session.rollback()
            total_stats['files_failed'] += 1
            failed_files.append((file.filename, str(e)))
            debug_log.error(f"ERROR en archivo {getattr(file, 'filename', '?')}: {e}")
            debug_log.error(traceback.format_exc())

            if filepath and os.path.exists(filepath):
                os.remove(filepath)

    debug_log.info(f"{'='*60}")
    debug_log.info(f"RESUMEN FINAL: processed={total_stats['files_processed']}, failed={total_stats['files_failed']}")
    debug_log.info(f"  trans={total_stats['transactions_created']}, holdings={total_stats['holdings_created']}, divs={total_stats['dividends_created']}")
    debug_log.info(f"  deposits={total_stats.get('deposits_created', 0)}, fees={total_stats.get('fees_created', 0)}")
    if total_stats.get('deposits_skipped'):
        debug_log.warning(f"Depósitos no importados ({len(total_stats['deposits_skipped'])}):")
        for entry in total_stats['deposits_skipped']:
            debug_log.warning(f"  - {entry}")
    if failed_files:
        debug_log.warning(f"Archivos fallidos: {failed_files}")

    if total_stats['files_processed'] > 0:
        # Nuevo flujo: encolar rebuild FULL (worker en cron).
        # FULL domina NOW y reemplaza los invalidates/recompute en la request.
        from app.services.cache_rebuild_state_service import CacheRebuildStateService

        CacheRebuildStateService.mark_full_history(current_user.id)

    from urllib.parse import urlencode

    if total_stats['files_processed'] > 0:
        query_params = {
            'success': 1,
            'files': total_stats['files_processed'],
            'trans': total_stats['transactions_created'],
            'holdings': total_stats['holdings_created'],
            'divs': total_stats['dividends_created'],
            'fees': total_stats.get('fees_created', 0),
            'deps': total_stats.get('deposits_created', 0),
            'withs': total_stats.get('withdrawals_created', 0),
            'enrich': total_stats.get('enrichment_success', 0),
            'enrich_total': total_stats.get('enrichment_needed', 0),
            'skipped': total_stats.get('transactions_skipped', 0),
            'dep_skip': len(total_stats.get('deposits_skipped', [])),
        }

        set_import_progress(current_user.id, {
            'phase': 'completed',
            'stats': total_stats
        })

        redirect_url = url_for('portfolio.import_csv') + '?' + urlencode(query_params)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'success': True, 'redirect_url': redirect_url}), 200

        return redirect(redirect_url)

    if total_stats['files_failed'] > 0:
        error_msgs = ' | '.join([f"{fname}: {err[:50]}" for fname, err in failed_files[:3]])
        query_params = {
            'error': 1,
            'files_failed': total_stats['files_failed'],
            'error_msg': error_msgs
        }
        redirect_url = url_for('portfolio.import_csv') + '?' + urlencode(query_params)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'redirect_url': redirect_url}), 200

        return redirect(redirect_url)

    flash('❌ No se pudo importar ningún archivo', 'error')
    return redirect(url_for('portfolio.import_csv'))
