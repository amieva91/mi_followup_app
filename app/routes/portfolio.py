"""
Rutas para gestión de portfolio
"""
from flask import render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
import os
import time
from threading import Lock
from app.routes import portfolio_bp
from app import db

# Cache global para progreso de importación (thread-safe)
import_progress_cache = {}
progress_lock = Lock()
from app.models import (
    BrokerAccount, Asset, PortfolioHolding, 
    Transaction, Broker
)
from app.forms import (
    BrokerAccountForm, ManualTransactionForm
)
from app.services.csv_detector import detect_and_parse
from app.services.importer_v2 import CSVImporterV2

# Configuración de uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}


@portfolio_bp.route('/')
@login_required
def dashboard():
    """Dashboard del portfolio con holdings unificados"""
    from collections import defaultdict
    
    # Obtener todas las cuentas del usuario
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    # Obtener todos los holdings individuales
    all_holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    # Agrupar por asset_id (unificar)
    grouped = defaultdict(lambda: {
        'asset': None,
        'total_quantity': 0,
        'total_cost': 0,
        'accounts': [],
        'first_purchase_date': None,
        'last_transaction_date': None
    })
    
    for holding in all_holdings:
        asset_id = holding.asset_id
        group = grouped[asset_id]
        
        # Datos del asset
        if group['asset'] is None:
            group['asset'] = holding.asset
        
        # Sumar cantidades y costes
        group['total_quantity'] += holding.quantity
        group['total_cost'] += holding.total_cost
        
        # Agregar cuenta a la lista
        group['accounts'].append({
            'broker': holding.account.broker.name,
            'account_name': holding.account.account_name,
            'quantity': holding.quantity,
            'average_buy_price': holding.average_buy_price
        })
        
        # Fechas
        if group['first_purchase_date'] is None or holding.first_purchase_date < group['first_purchase_date']:
            group['first_purchase_date'] = holding.first_purchase_date
        
        if group['last_transaction_date'] is None or holding.last_transaction_date > group['last_transaction_date']:
            group['last_transaction_date'] = holding.last_transaction_date
    
    # Convertir a lista
    holdings_unified = []
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['asset_id'] = asset_id
        holdings_unified.append(data)
    
    # Calcular totales
    total_value = 0  # Por ahora sin precios
    total_cost = sum(h['total_cost'] for h in holdings_unified)
    total_pl = 0
    total_pl_pct = 0
    
    return render_template(
        'portfolio/dashboard.html',
        accounts=accounts,
        holdings=holdings_unified,
        total_value=total_value,
        total_cost=total_cost,
        total_pl=total_pl,
        total_pl_pct=total_pl_pct,
        unified=True  # Flag para indicar que son holdings unificados
    )


@portfolio_bp.route('/accounts')
@login_required
def accounts_list():
    """Lista de cuentas del usuario"""
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    return render_template('portfolio/accounts.html', accounts=accounts)


@portfolio_bp.route('/accounts/new', methods=['GET', 'POST'])
@login_required
def account_new():
    """Crear nueva cuenta de broker"""
    form = BrokerAccountForm()
    
    if form.validate_on_submit():
        account = BrokerAccount(
            user_id=current_user.id,
            broker_id=form.broker_id.data,
            account_name=form.account_name.data,
            account_number=form.account_number.data,
            base_currency=form.base_currency.data
        )
        db.session.add(account)
        db.session.commit()
        
        flash(f'✅ Cuenta "{account.account_name}" creada correctamente', 'success')
        return redirect(url_for('portfolio.accounts_list'))
    
    return render_template('portfolio/account_form.html', form=form, title='Nueva Cuenta')


@portfolio_bp.route('/accounts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def account_edit(id):
    """Editar cuenta de broker"""
    account = BrokerAccount.query.get_or_404(id)
    
    if account.user_id != current_user.id:
        flash('No tienes permiso para editar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))
    
    form = BrokerAccountForm(obj=account)
    
    if form.validate_on_submit():
        account.broker_id = form.broker_id.data
        account.account_name = form.account_name.data
        account.account_number = form.account_number.data
        account.base_currency = form.base_currency.data
        
        db.session.commit()
        flash(f'✅ Cuenta actualizada correctamente', 'success')
        return redirect(url_for('portfolio.accounts_list'))
    
    return render_template('portfolio/account_form.html', form=form, title='Editar Cuenta', account=account)


@portfolio_bp.route('/accounts/<int:id>/clear', methods=['POST'])
@login_required
def account_clear(id):
    """Vaciar cuenta de broker (borrar datos pero mantener la cuenta)"""
    account = BrokerAccount.query.get_or_404(id)
    
    if account.user_id != current_user.id:
        flash('❌ No tienes permiso para modificar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))
    
    # Contar datos antes de borrar
    num_holdings = PortfolioHolding.query.filter_by(account_id=id).count()
    num_transactions = Transaction.query.filter_by(account_id=id).count()
    
    account_name = account.account_name
    
    # Borrar SOLO los datos, NO la cuenta
    # 1. Borrar métricas
    from app.models.metrics import PortfolioMetrics
    PortfolioMetrics.query.filter_by(account_id=id).delete()
    
    # 2. Borrar cash flows
    from app.models.transaction import CashFlow
    CashFlow.query.filter_by(account_id=id).delete()
    
    # 3. Borrar transacciones
    Transaction.query.filter_by(account_id=id).delete()
    
    # 4. Borrar holdings
    PortfolioHolding.query.filter_by(account_id=id).delete()
    
    # 5. Resetear valores de la cuenta
    account.current_cash = 0.0
    account.margin_used = 0.0
    
    db.session.commit()
    
    flash(
        f'🧹 Cuenta "{account_name}" vaciada correctamente. '
        f'Se eliminaron {num_transactions} transacciones y {num_holdings} posiciones.',
        'success'
    )
    return redirect(url_for('portfolio.accounts_list'))


@portfolio_bp.route('/accounts/<int:id>/delete', methods=['POST'])
@login_required
def account_delete(id):
    """Eliminar cuenta de broker y todos sus datos asociados"""
    account = BrokerAccount.query.get_or_404(id)
    
    if account.user_id != current_user.id:
        flash('❌ No tienes permiso para eliminar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))
    
    # Contar datos asociados para mostrar en el mensaje
    num_holdings = PortfolioHolding.query.filter_by(account_id=id).count()
    num_transactions = Transaction.query.filter_by(account_id=id).count()
    
    account_name = account.account_name
    
    # Borrar en cascada manual (por si las FK no tienen CASCADE)
    # 1. Borrar métricas
    from app.models.metrics import PortfolioMetrics
    PortfolioMetrics.query.filter_by(account_id=id).delete()
    
    # 2. Borrar cash flows
    from app.models.transaction import CashFlow
    CashFlow.query.filter_by(account_id=id).delete()
    
    # 3. Borrar transacciones
    Transaction.query.filter_by(account_id=id).delete()
    
    # 4. Borrar holdings
    PortfolioHolding.query.filter_by(account_id=id).delete()
    
    # 5. Borrar la cuenta
    db.session.delete(account)
    db.session.commit()
    
    flash(
        f'🗑️ Cuenta "{account_name}" eliminada permanentemente. '
        f'Se borraron {num_transactions} transacciones y {num_holdings} posiciones.',
        'success'
    )
    return redirect(url_for('portfolio.accounts_list'))


@portfolio_bp.route('/holdings')
@login_required
def holdings_list():
    """Lista de posiciones actuales (agrupadas por asset)"""
    from collections import defaultdict
    
    # Obtener todos los holdings
    all_holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    # Agrupar por asset_id
    grouped = defaultdict(lambda: {
        'asset': None,
        'total_quantity': 0,
        'total_cost': 0,
        'accounts': [],
        'first_purchase_date': None,
        'last_transaction_date': None
    })
    
    for holding in all_holdings:
        asset_id = holding.asset_id
        group = grouped[asset_id]
        
        # Datos del asset (tomar del primer holding)
        if group['asset'] is None:
            group['asset'] = holding.asset
        
        # Sumar cantidades y costes
        group['total_quantity'] += holding.quantity
        group['total_cost'] += holding.total_cost
        
        # Agregar cuenta a la lista
        group['accounts'].append({
            'broker': holding.account.broker.name,
            'account_name': holding.account.account_name,
            'quantity': holding.quantity,
            'average_buy_price': holding.average_buy_price
        })
        
        # Fechas (usar la más antigua para first_purchase y la más reciente para last_transaction)
        if group['first_purchase_date'] is None or holding.first_purchase_date < group['first_purchase_date']:
            group['first_purchase_date'] = holding.first_purchase_date
        
        if group['last_transaction_date'] is None or holding.last_transaction_date > group['last_transaction_date']:
            group['last_transaction_date'] = holding.last_transaction_date
    
    # Convertir a lista y calcular precio medio ponderado
    holdings_unified = []
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['asset_id'] = asset_id
        holdings_unified.append(data)
    
    # Ordenar por símbolo
    holdings_unified.sort(key=lambda x: x['asset'].symbol if x['asset'] else '')
    
    return render_template('portfolio/holdings.html', holdings=holdings_unified, unified=True)


@portfolio_bp.route('/transactions')
@login_required
def transactions_list():
    """Lista de transacciones con filtros"""
    from datetime import datetime
    
    # Query base
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Aplicar filtros
    filtered = False
    
    # Filtro por símbolo o ISIN
    symbol = request.args.get('symbol', '').strip()
    if symbol:
        filtered = True
        # Buscar assets que coincidan con el símbolo o ISIN
        assets = Asset.query.filter(
            db.or_(
                Asset.symbol.ilike(f'%{symbol}%'),
                Asset.isin.ilike(f'%{symbol}%')
            )
        ).all()
        asset_ids = [a.id for a in assets]
        if asset_ids:
            query = query.filter(Transaction.asset_id.in_(asset_ids))
        else:
            # No hay assets que coincidan, retornar lista vacía
            query = query.filter(Transaction.asset_id == -1)
    
    # Filtro por tipo de transacción
    txn_type = request.args.get('type', '').strip()
    if txn_type:
        filtered = True
        query = query.filter_by(transaction_type=txn_type)
    
    # Filtro por cuenta
    account_id = request.args.get('account', '').strip()
    if account_id:
        filtered = True
        try:
            query = query.filter_by(account_id=int(account_id))
        except ValueError:
            pass
    
    # Filtro por fecha desde
    date_from = request.args.get('date_from', '').strip()
    if date_from:
        filtered = True
        try:
            date_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date >= date_obj)
        except ValueError:
            pass
    
    # Filtro por fecha hasta
    date_to = request.args.get('date_to', '').strip()
    if date_to:
        filtered = True
        try:
            date_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date <= date_obj)
        except ValueError:
            pass
    
    # Filtro: Dividendos a revisar (dividendos no EUR)
    dividends_review = request.args.get('dividends_review', '').strip()
    if dividends_review:
        filtered = True
        query = query.filter(
            Transaction.transaction_type == 'DIVIDEND',
            Transaction.currency != 'EUR'
        )
    
    # Filtro: Assets sin enriquecer (sin symbol o sin ibkr_exchange en AssetRegistry)
    unenriched_assets = request.args.get('unenriched_assets', '').strip()
    if unenriched_assets:
        from app.models import AssetRegistry
        filtered = True
        
        # Buscar assets que necesitan enriquecimiento
        unenriched_registries = AssetRegistry.query.filter(
            db.or_(
                AssetRegistry.symbol.is_(None),
                AssetRegistry.ibkr_exchange.is_(None)
            )
        ).all()
        
        # Obtener ISINs
        unenriched_isins = [r.isin for r in unenriched_registries]
        
        # Filtrar transacciones de esos assets
        if unenriched_isins:
            assets = Asset.query.filter(Asset.isin.in_(unenriched_isins)).all()
            asset_ids = [a.id for a in assets]
            if asset_ids:
                query = query.filter(Transaction.asset_id.in_(asset_ids))
            else:
                query = query.filter(Transaction.asset_id == -1)
        else:
            query = query.filter(Transaction.asset_id == -1)
    
    # Ordenamiento dinámico
    sort_by = request.args.get('sort_by', 'transaction_date').strip()
    sort_order = request.args.get('sort_order', 'desc').strip()
    
    # Mapeo de campos de ordenamiento
    sort_fields = {
        'transaction_date': Transaction.transaction_date,
        'transaction_type': Transaction.transaction_type,
        'amount': Transaction.amount,
        'asset': Asset.symbol,  # Join con Asset
        'account': BrokerAccount.account_name  # Join con BrokerAccount
    }
    
    # Aplicar joins si es necesario
    if sort_by in ['asset', 'account']:
        if sort_by == 'asset':
            query = query.outerjoin(Asset, Transaction.asset_id == Asset.id)
        elif sort_by == 'account':
            query = query.join(BrokerAccount, Transaction.account_id == BrokerAccount.id)
    
    # Aplicar ordenamiento
    if sort_by in sort_fields:
        order_field = sort_fields[sort_by]
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())
    else:
        # Ordenamiento por defecto
        query = query.order_by(Transaction.transaction_date.desc())
    
    # SIN LÍMITE - Mostrar todas las transacciones
    transactions = query.all()
    
    # Obtener todas las cuentas para el selector
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(BrokerAccount.broker_id, BrokerAccount.account_name).all()
    
    return render_template('portfolio/transactions.html', 
                          transactions=transactions,
                          accounts=accounts,
                          filtered=filtered)


@portfolio_bp.route('/asset-registry')
@login_required
def asset_registry():
    """
    Gestión completa de AssetRegistry - Tabla global compartida
    """
    from app.models import AssetRegistry
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
    
    # Filtro: Solo sin enriquecer (condiciones unificadas: sin symbol O sin MIC)
    unenriched_only = request.args.get('unenriched_only', '').strip()
    if unenriched_only:
        query = query.filter(
            db.or_(
                AssetRegistry.symbol.is_(None),
                AssetRegistry.mic.is_(None)
            )
        )
    
    # Ordenamiento
    sort_by = request.args.get('sort_by', 'created_at').strip()
    sort_order = request.args.get('sort_order', 'desc').strip()
    
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
    
    if sort_by in sort_fields:
        order_field = sort_fields[sort_by]
        if sort_order == 'asc':
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
    
    # Generar CSRF token para el template
    from flask_wtf.csrf import generate_csrf
    
    return render_template('portfolio/asset_registry.html',
                          registries=registries,
                          stats=stats,
                          sort_by=sort_by,
                          sort_order=sort_order,
                          csrf_token=generate_csrf())


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
    
    db.session.commit()
    
    flash(f'✅ Registro actualizado: {registry.isin}', 'success')
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


@portfolio_bp.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def transaction_edit(id):
    """Editar transacción existente"""
    transaction = Transaction.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()
    
    form = ManualTransactionForm()
    
    # Poblar choices dinámicamente
    form.account_id.choices = [
        (acc.id, f'{acc.broker.name} - {acc.account_name}')
        for acc in BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    ]
    
    if form.validate_on_submit():
        # Actualizar datos del asset si cambió
        asset = transaction.asset
        if asset:
            asset.symbol = form.symbol.data
            asset.isin = form.isin.data if form.isin.data else asset.isin
            asset.name = form.asset_name.data
            asset.asset_type = form.asset_type.data
            asset.currency = form.currency.data
            # Actualizar identificadores de mercado
            asset.exchange = form.exchange.data if form.exchange.data else asset.exchange
            asset.mic = form.mic.data if form.mic.data else asset.mic
            asset.yahoo_suffix = form.yahoo_suffix.data if form.yahoo_suffix.data else asset.yahoo_suffix
        
        # Actualizar transacción
        old_account_id = transaction.account_id
        transaction.account_id = form.account_id.data
        transaction.transaction_type = form.transaction_type.data
        transaction.transaction_date = form.transaction_date.data
        transaction.quantity = form.quantity.data
        transaction.price = form.price.data
        transaction.amount = form.quantity.data * form.price.data
        transaction.currency = form.currency.data
        transaction.commission = form.commission.data
        transaction.fees = form.fees.data
        transaction.tax = form.tax.data
        transaction.notes = form.notes.data
        
        db.session.commit()
        
        # Recalcular holdings de la(s) cuenta(s) afectada(s)
        from app.services.importer_v2 import CSVImporterV2
        
        # Recalcular cuenta antigua si cambió
        if old_account_id != transaction.account_id:
            importer_old = CSVImporterV2(current_user.id, old_account_id)
            importer_old._recalculate_holdings()
        
        # Recalcular cuenta actual
        importer = CSVImporterV2(current_user.id, transaction.account_id)
        importer._recalculate_holdings()
        
        db.session.commit()
        
        flash('✅ Transacción actualizada correctamente. Holdings recalculados.', 'success')
        return redirect(url_for('portfolio.transactions_list'))
    
    # Prellenar formulario en GET
    if request.method == 'GET' and transaction.asset:
        form.account_id.data = transaction.account_id
        form.symbol.data = transaction.asset.symbol
        form.isin.data = transaction.asset.isin
        form.asset_name.data = transaction.asset.name
        form.asset_type.data = transaction.asset.asset_type
        form.currency.data = transaction.currency
        # Identificadores de mercado
        form.exchange.data = transaction.asset.exchange
        form.mic.data = transaction.asset.mic
        form.yahoo_suffix.data = transaction.asset.yahoo_suffix
        # Datos de transacción
        form.transaction_type.data = transaction.transaction_type
        form.transaction_date.data = transaction.transaction_date
        form.quantity.data = transaction.quantity
        form.price.data = float(transaction.price) if transaction.price else 0
        form.commission.data = float(transaction.commission) if transaction.commission else 0
        form.fees.data = float(transaction.fees) if transaction.fees else 0
        form.tax.data = float(transaction.tax) if transaction.tax else 0
        form.notes.data = transaction.notes
    
    return render_template('portfolio/transaction_form.html', 
                          form=form, 
                          title='Editar Transacción',
                          action='edit')


@portfolio_bp.route('/transactions/new', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Registrar nueva transacción manual"""
    form = ManualTransactionForm()
    
    if form.validate_on_submit():
        # Buscar o crear el activo
        asset = Asset.query.filter_by(symbol=form.symbol.data, currency=form.currency.data).first()
        if not asset:
            asset = Asset(
                symbol=form.symbol.data,
                isin=form.isin.data,
                name=form.asset_name.data,
                asset_type=form.asset_type.data,
                currency=form.currency.data,
                exchange=form.exchange.data,
                mic=form.mic.data,
                yahoo_suffix=form.yahoo_suffix.data
            )
            db.session.add(asset)
            db.session.flush()
        else:
            # Actualizar asset existente con nuevos datos si se proporcionan
            if form.exchange.data:
                asset.exchange = form.exchange.data
            if form.mic.data:
                asset.mic = form.mic.data
            if form.yahoo_suffix.data:
                asset.yahoo_suffix = form.yahoo_suffix.data
        
        # Calcular monto
        amount = form.quantity.data * form.price.data
        if form.transaction_type.data == 'BUY':
            amount = -amount  # Compra es negativo (sale dinero)
        
        # Crear transacción
        transaction = Transaction(
            user_id=current_user.id,
            account_id=form.account_id.data,
            asset_id=asset.id,
            transaction_type=form.transaction_type.data,
            transaction_date=datetime.combine(form.transaction_date.data, datetime.min.time()),
            settlement_date=form.transaction_date.data,
            quantity=form.quantity.data,
            price=form.price.data,
            amount=amount,
            currency=form.currency.data,
            commission=form.commission.data,
            fees=form.fees.data,
            tax=form.tax.data,
            notes=form.notes.data,
            source='MANUAL'
        )
        db.session.add(transaction)
        
        # Actualizar o crear holding
        holding = PortfolioHolding.query.filter_by(
            user_id=current_user.id,
            account_id=form.account_id.data,
            asset_id=asset.id
        ).first()
        
        if form.transaction_type.data == 'BUY':
            if holding:
                # Actualizar holding existente
                holding.add_purchase(
                    quantity=form.quantity.data,
                    price=form.price.data,
                    total_cost=abs(amount) + form.commission.data + form.fees.data + form.tax.data
                )
                holding.last_transaction_date = form.transaction_date.data
            else:
                # Crear nuevo holding
                total_cost = abs(amount) + form.commission.data + form.fees.data + form.tax.data
                holding = PortfolioHolding(
                    user_id=current_user.id,
                    account_id=form.account_id.data,
                    asset_id=asset.id,
                    quantity=form.quantity.data,
                    average_buy_price=form.price.data,
                    total_cost=total_cost,
                    first_purchase_date=form.transaction_date.data,
                    last_transaction_date=form.transaction_date.data
                )
                db.session.add(holding)
        
        elif form.transaction_type.data == 'SELL':
            if holding:
                # Calcular P&L (simplificado por ahora)
                cost_basis = holding.average_buy_price * form.quantity.data
                revenue = abs(amount) - form.commission.data - form.fees.data - form.tax.data
                realized_pl = revenue - cost_basis
                transaction.realized_pl = realized_pl
                
                if cost_basis > 0:
                    transaction.realized_pl_pct = (realized_pl / cost_basis) * 100
                
                # Actualizar holding
                holding.subtract_sale(form.quantity.data, realized_pl)
                holding.last_transaction_date = form.transaction_date.data
        
        db.session.commit()
        
        flash(f'✅ Transacción de {form.transaction_type.data} registrada correctamente', 'success')
        return redirect(url_for('portfolio.transactions_list'))
    
    return render_template('portfolio/transaction_form.html', form=form, title='Nueva Transacción')


# ==================== CSV IMPORT ====================

def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@portfolio_bp.route('/import')
@login_required
def import_csv():
    """Formulario para subir CSV"""
    # Obtener cuentas del usuario
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    return render_template('portfolio/import_csv.html', accounts=accounts, title='Importar CSV')


@portfolio_bp.route('/import/progress')
@login_required
def import_progress():
    """Endpoint para consultar progreso de importación en tiempo real"""
    user_key = f"user_{current_user.id}"
    
    with progress_lock:
        progress = import_progress_cache.get(user_key, {})
    
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
        # Info de archivos
        'current_file': progress.get('current_file'),
        'file_number': progress.get('file_number'),
        'total_files': progress.get('total_files'),
        'completed_files': progress.get('completed_files', []),
        'pending_files': progress.get('pending_files', [])
    })


@portfolio_bp.route('/import/process', methods=['POST'])
@login_required
def import_csv_process():
    """Procesa uno o múltiples archivos CSV subidos"""
    # Verificar que se enviaron archivos
    if 'csv_files' not in request.files:
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    files = request.files.getlist('csv_files')
    
    if not files or len(files) == 0 or files[0].filename == '':
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    # Validar que todos son CSV
    for file in files:
        if not allowed_file(file.filename):
            flash(f'❌ Archivo no válido: {file.filename} (solo se permiten archivos CSV)', 'error')
            return redirect(url_for('portfolio.import_csv'))
    
    # Obtener cuenta seleccionada
    account_id = request.form.get('account_id')
    if not account_id:
        flash('❌ Debes seleccionar una cuenta', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    account = BrokerAccount.query.get(account_id)
    if not account or account.user_id != current_user.id:
        flash('❌ Cuenta no válida', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    # Asegurar que existe el directorio de uploads
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Procesar cada archivo
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
        'withdrawals_created': 0
    }
    
    failed_files = []
    completed_files = []
    total_files = len(files)
    
    for file_idx, file in enumerate(files):
        filepath = None
        try:
            # file_idx es 0-based, file_number es 1-based para mostrar
            file_number = file_idx + 1
            
            # Guardar archivo temporalmente
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"temp_{current_user.id}_{filename}")
            file.save(filepath)
            print(f"\n📊 DEBUG: Archivo guardado: {filepath}")
            
            # Detectar y parsear
            print(f"📊 DEBUG: Detectando formato del CSV...")
            parsed_data = detect_and_parse(filepath)
            print(f"📊 DEBUG: CSV parseado correctamente. Formato: {parsed_data.get('format', 'unknown')}")
            
            # Importar a BD con AssetRegistry (cache global)
            print(f"\n📊 DEBUG: Iniciando importación para archivo: {filename}")
            importer = CSVImporterV2(user_id=current_user.id, broker_account_id=account.id)
            
            # Callback de progreso (almacenar en cache global thread-safe)
            user_key = f"user_{current_user.id}"
            
            # Lista de archivos pendientes (excluye el actual)
            pending_files = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
            
            def progress_callback(current, total, message):
                # Recalcular pendientes cada vez (excluye el actual)
                remaining = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
                
                with progress_lock:
                    import_progress_cache[user_key] = {
                        'current': current,
                        'total': total,
                        'message': message,
                        'percentage': int((current / total) * 100) if total > 0 else 0,
                        'current_file': filename,
                        'file_number': file_number,
                        'total_files': total_files,
                        'completed_files': completed_files.copy(),
                        'pending_files': remaining.copy()
                    }
                    print(f"   📊 DEBUG Progress: {file_number}/{total_files}, completed={completed_files}, pending={remaining}")
            
            # Importar con progreso
            print(f"📊 DEBUG: Llamando a importer.import_data()...")
            stats = importer.import_data(parsed_data, progress_callback=progress_callback)
            print(f"📊 DEBUG: Importación completada. Stats: {stats}")
            
            # Añadir archivo a completados
            completed_files.append(filename)
            print(f"📊 DEBUG: Archivo añadido a completados: {filename}")
            print(f"📊 DEBUG: Lista de completados ahora: {completed_files}")
            
            # Actualizar progreso para mostrar el archivo como completado
            # ANTES de pasar al siguiente archivo
            with progress_lock:
                remaining = [secure_filename(files[i].filename) for i in range(file_idx + 1, len(files))]
                import_progress_cache[user_key] = {
                    'phase': 'file_completed',
                    'current_file': filename,
                    'file_number': file_number,
                    'total_files': total_files,
                    'completed_files': completed_files.copy(),
                    'pending_files': remaining,
                    'message': f'✅ {filename} importado correctamente'
                }
            
            # Breve pausa para que el frontend lea el estado "completado"
            time.sleep(0.3)
            
            # Acumular estadísticas
            total_stats['files_processed'] += 1
            total_stats['transactions_created'] += stats['transactions_created']
            total_stats['holdings_created'] += stats['holdings_created']
            total_stats['dividends_created'] += stats['dividends_created']
            total_stats['assets_created'] += stats['assets_created']
            total_stats['fees_created'] += stats.get('fees_created', 0)
            total_stats['deposits_created'] += stats.get('deposits_created', 0)
            total_stats['withdrawals_created'] += stats.get('withdrawals_created', 0)
            
            # Estadísticas de AssetRegistry
            if 'enrichment_needed' not in total_stats:
                total_stats['enrichment_needed'] = 0
                total_stats['enrichment_success'] = 0
                total_stats['enrichment_failed'] = 0
            
            total_stats['enrichment_needed'] += stats.get('enrichment_needed', 0)
            total_stats['enrichment_success'] += stats.get('enrichment_success', 0)
            total_stats['enrichment_failed'] += stats.get('enrichment_failed', 0)
            
            # Eliminar archivo temporal
            if os.path.exists(filepath):
                os.remove(filepath)
                
        except Exception as e:
            # Registrar archivo fallido
            print(f"\n❌ ERROR importando {file.filename}:")
            print(f"   Tipo de error: {type(e).__name__}")
            print(f"   Mensaje: {str(e)}")
            import traceback
            print(f"   Traceback:\n{traceback.format_exc()}")
            
            # IMPORTANTE: Rollback de la sesión para evitar PendingRollbackError en imports posteriores
            db.session.rollback()
            print(f"   🔄 Session rolled back después del error")
            
            total_stats['files_failed'] += 1
            failed_files.append((file.filename, str(e)))
            
            # Eliminar archivo temporal si existe
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
    
    # Pasar estadísticas por URL (no por session/flash para evitar exceder límite de cookie)
    print(f"\n📊 DEBUG: Preparando redirect con stats: {total_stats}")
    
    if total_stats['files_processed'] > 0:
        # Construir query params con las estadísticas
        from urllib.parse import urlencode
        
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
        }
        
        # Añadir a session SOLO para el endpoint de progreso (stats detallados)
        user_key = f"user_{current_user.id}"
        with progress_lock:
            import_progress_cache[user_key] = {
                'phase': 'completed',
                'stats': total_stats
            }
        
        redirect_url = url_for('portfolio.import_csv') + '?' + urlencode(query_params)
        print(f"📊 DEBUG: Redirigiendo a: {redirect_url}")
        print(f"📊 DEBUG: Verificar transacciones en BD...")
        
        # Debug: Verificar que se guardaron las transacciones
        from app.models import Transaction
        trans_count = Transaction.query.filter_by(user_id=current_user.id).count()
        print(f"📊 DEBUG: Transacciones en BD para usuario {current_user.id}: {trans_count}")
        
        return redirect(redirect_url)
    
    if total_stats['files_failed'] > 0:
        from urllib.parse import urlencode, quote
        
        # Construir mensaje de error para query params
        error_msgs = ' | '.join([f"{fname}: {err[:50]}" for fname, err in failed_files[:3]])  # Limitar a 3 primeros
        
        query_params = {
            'error': 1,
            'files_failed': total_stats['files_failed'],
            'error_msg': error_msgs
        }
        
        return redirect(url_for('portfolio.import_csv') + '?' + urlencode(query_params))
    
    flash('❌ No se pudo importar ningún archivo', 'error')
    return redirect(url_for('portfolio.import_csv'))

@portfolio_bp.route('/mappings')
@login_required
def mappings():
    """
    Página de gestión de mapeos (MIC→Yahoo, Exchange→Yahoo, DeGiro→IBKR)
    """
    from app.models import MappingRegistry
    from flask_wtf.csrf import generate_csrf
    
    # Filtros
    search = request.args.get('search', '').strip()
    mapping_type_filter = request.args.get('mapping_type', '').strip()
    country_filter = request.args.get('country', '').strip()
    
    # Query base
    query = MappingRegistry.query
    
    # Aplicar filtros
    if search:
        query = query.filter(
            db.or_(
                MappingRegistry.source_key.ilike(f'%{search}%'),
                MappingRegistry.target_value.ilike(f'%{search}%'),
                MappingRegistry.description.ilike(f'%{search}%')
            )
        )
    
    if mapping_type_filter:
        query = query.filter_by(mapping_type=mapping_type_filter)
    
    if country_filter:
        query = query.filter_by(country=country_filter)
    
    # Ordenar
    query = query.order_by(MappingRegistry.mapping_type, MappingRegistry.source_key)
    
    mappings = query.all()
    
    # Estadísticas
    stats = {
        'total': MappingRegistry.query.count(),
        'mic_to_yahoo': MappingRegistry.query.filter_by(mapping_type='MIC_TO_YAHOO').count(),
        'exchange_to_yahoo': MappingRegistry.query.filter_by(mapping_type='EXCHANGE_TO_YAHOO').count(),
        'degiro_to_ibkr': MappingRegistry.query.filter_by(mapping_type='DEGIRO_TO_IBKR').count(),
        'active': MappingRegistry.query.filter_by(is_active=True).count(),
        'inactive': MappingRegistry.query.filter_by(is_active=False).count(),
    }
    
    # Países únicos para el filtro
    countries = db.session.query(MappingRegistry.country).distinct().filter(
        MappingRegistry.country.isnot(None)
    ).order_by(MappingRegistry.country).all()
    countries = [c[0] for c in countries]
    
    return render_template('portfolio/mappings.html',
                          mappings=mappings,
                          stats=stats,
                          countries=countries,
                          csrf_token=generate_csrf())


@portfolio_bp.route('/mappings/new', methods=['POST'])
@login_required
def mappings_new():
    """
    Crear nuevo mapeo
    """
    from app.models import MappingRegistry
    from flask_wtf.csrf import validate_csrf
    
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))
    
    mapping_type = request.form.get('mapping_type', '').strip()
    source_key = request.form.get('source_key', '').strip().upper()
    target_value = request.form.get('target_value', '').strip()
    description = request.form.get('description', '').strip()
    country = request.form.get('country', '').strip().upper() or None
    
    if not mapping_type or not source_key or not target_value:
        flash('❌ Faltan campos obligatorios (Tipo, Clave, Valor)', 'error')
        return redirect(url_for('portfolio.mappings'))
    
    # Verificar si ya existe
    existing = MappingRegistry.query.filter_by(
        mapping_type=mapping_type,
        source_key=source_key
    ).first()
    
    if existing:
        flash(f'❌ Ya existe un mapeo {mapping_type}: {source_key}', 'error')
        return redirect(url_for('portfolio.mappings'))
    
    # Crear nuevo
    mapping = MappingRegistry(
        mapping_type=mapping_type,
        source_key=source_key,
        target_value=target_value,
        description=description,
        country=country,
        created_by='MANUAL'
    )
    
    db.session.add(mapping)
    db.session.commit()
    
    flash(f'✅ Mapeo creado: {source_key} → {target_value}', 'success')
    return redirect(url_for('portfolio.mappings'))


@portfolio_bp.route('/mappings/<int:id>/edit', methods=['POST'])
@login_required
def mappings_edit(id):
    """
    Editar mapeo existente
    """
    from app.models import MappingRegistry
    from flask_wtf.csrf import validate_csrf
    
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))
    
    mapping = MappingRegistry.query.get_or_404(id)
    
    # Actualizar campos editables
    mapping.target_value = request.form.get('target_value', '').strip()
    mapping.description = request.form.get('description', '').strip()
    mapping.country = request.form.get('country', '').strip().upper() or None
    
    db.session.commit()
    
    flash(f'✅ Mapeo actualizado: {mapping.source_key} → {mapping.target_value}', 'success')
    return redirect(url_for('portfolio.mappings'))


@portfolio_bp.route('/mappings/<int:id>/delete', methods=['POST'])
@login_required
def mappings_delete(id):
    """
    Eliminar mapeo
    """
    from app.models import MappingRegistry
    from flask_wtf.csrf import validate_csrf
    
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))
    
    mapping = MappingRegistry.query.get_or_404(id)
    source_key = mapping.source_key
    
    db.session.delete(mapping)
    db.session.commit()
    
    flash(f'🗑️ Mapeo eliminado: {source_key}', 'info')
    return redirect(url_for('portfolio.mappings'))


@portfolio_bp.route('/mappings/<int:id>/toggle', methods=['POST'])
@login_required
def mappings_toggle(id):
    """
    Activar/desactivar mapeo
    """
    from app.models import MappingRegistry
    from flask_wtf.csrf import validate_csrf
    
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))
    
    mapping = MappingRegistry.query.get_or_404(id)
    mapping.is_active = not mapping.is_active
    
    db.session.commit()
    
    status = 'activado' if mapping.is_active else 'desactivado'
    flash(f'✅ Mapeo {status}: {mapping.source_key}', 'success')
    return redirect(url_for('portfolio.mappings'))

