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

# Cache global para progreso de actualización de precios (thread-safe)
price_update_progress_cache = {}
price_progress_lock = Lock()
from app.models import (
    BrokerAccount, Asset, PortfolioHolding, 
    Transaction, Broker
)
from app.forms import (
    BrokerAccountForm, ManualTransactionForm
)
from app.services.csv_detector import detect_and_parse
from app.services.importer_v2 import CSVImporterV2
from app.services.metrics import BasicMetrics

# Configuración de uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

# Importar servicio de conversión de divisas (con cache y API del BCE)
from app.services.currency_service import convert_to_eur


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
    
    # Obtener última sincronización (última transacción creada)
    last_sync = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).first()
    
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
        
        # Crear lista de brokers únicos para display
        brokers_set = set()
        for acc in data['accounts']:
            brokers_set.add(acc['broker'])
        data['brokers'] = sorted(list(brokers_set))
        
        holdings_unified.append(data)
    
    # Calcular totales con precios actuales (Sprint 3 Final)
    total_value = 0
    total_cost = 0  # Será calculado en EUR
    total_pl = 0
    last_price_update = None
    
    for h in holdings_unified:
        asset = h['asset']
        
        # Convertir coste a EUR (SIEMPRE, incluso sin precio actual)
        cost_eur = convert_to_eur(h['total_cost'], asset.currency)
        h['cost_eur'] = cost_eur  # Guardar para el template
        total_cost += cost_eur
        
        if asset and asset.current_price:
            # Calcular valor actual en moneda local
            current_value_local = h['total_quantity'] * asset.current_price
            h['current_value_local'] = current_value_local
            h['local_currency'] = asset.currency
            
            # Convertir a EUR
            current_value_eur = convert_to_eur(current_value_local, asset.currency)
            h['current_value_eur'] = current_value_eur
            
            # Calcular P&L individual
            pl_individual = current_value_eur - cost_eur
            h['pl_eur'] = pl_individual  # Guardar para el template
            
            # Sumar al total (en EUR)
            total_value += current_value_eur
            total_pl += pl_individual
            
            # Última actualización de precios
            if asset.last_price_update:
                if last_price_update is None or asset.last_price_update > last_price_update:
                    last_price_update = asset.last_price_update
        else:
            # Si no hay precio, usar el coste en EUR como aproximación
            total_value += cost_eur
            h['pl_eur'] = 0  # Sin precio, P&L es 0
    
    # Calcular porcentaje
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0
    
    # Calcular peso % de cada holding
    for h in holdings_unified:
        if 'current_value_eur' in h and total_value > 0:
            h['weight_pct'] = (h['current_value_eur'] / total_value) * 100
        else:
            h['weight_pct'] = 0
    
    # Calcular métricas básicas (Sprint 4 - HITO 1 + Cache)
    from app.services.metrics.cache import MetricsCacheService
    
    # Intentar obtener del cache primero
    metrics = MetricsCacheService.get(current_user.id)
    
    if metrics is None:
        # Cache no existe o expiró - calcular desde cero
        metrics = BasicMetrics.get_all_metrics(
            current_user.id, 
            total_value, 
            total_cost, 
            total_pl
        )
        # Guardar en cache para próximas visitas
        MetricsCacheService.set(current_user.id, metrics)
    
    return render_template(
        'portfolio/dashboard.html',
        accounts=accounts,
        holdings=holdings_unified,
        total_value=total_value,
        total_cost=total_cost,
        total_pl=total_pl,
        total_pl_pct=total_pl_pct,
        last_price_update=last_price_update,
        last_sync=last_sync,
        unified=True,  # Flag para indicar que son holdings unificados
        metrics=metrics
    )


@portfolio_bp.route('/pl-by-asset')
@login_required
def pl_by_asset():
    """Vista de P&L histórico por asset/activo"""
    
    # Obtener P&L data (todo el histórico)
    pl_data = BasicMetrics.get_pl_by_asset(current_user.id)
    
    return render_template(
        'portfolio/pl_by_asset.html',
        pl_data=pl_data
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
    
    # 6. Invalidar cache de métricas después de eliminar todos los datos
    from app.services.metrics.cache import MetricsCacheService
    MetricsCacheService.invalidate(current_user.id)
    
    flash(
        f'🗑️ Cuenta "{account_name}" eliminada permanentemente. '
        f'Se borraron {num_transactions} transacciones y {num_holdings} posiciones.',
        'success'
    )
    return redirect(url_for('portfolio.accounts_list'))


@portfolio_bp.route('/currencies')
@login_required
def currencies():
    """Muestra tasas de conversión de monedas en portfolio"""
    from app.services.currency_service import get_cache_info, get_exchange_rates
    from collections import defaultdict
    
    # Obtener info del cache
    cache_info = get_cache_info()
    
    # Obtener todas las tasas actuales
    all_rates = get_exchange_rates()
    
    # Obtener monedas únicas en el portfolio del usuario
    user_currencies = db.session.query(Asset.currency, db.func.count(Asset.id)).join(
        PortfolioHolding, PortfolioHolding.asset_id == Asset.id
    ).filter(
        PortfolioHolding.user_id == current_user.id,
        PortfolioHolding.quantity > 0
    ).group_by(Asset.currency).all()
    
    # Nombres de monedas (parcial)
    currency_names = {
        'EUR': 'Euro',
        'USD': 'Dólar estadounidense',
        'GBP': 'Libra esterlina',
        'GBX': 'Penique británico',
        'JPY': 'Yen japonés',
        'CHF': 'Franco suizo',
        'AUD': 'Dólar australiano',
        'CAD': 'Dólar canadiense',
        'HKD': 'Dólar de Hong Kong',
        'SGD': 'Dólar de Singapur',
        'NOK': 'Corona noruega',
        'SEK': 'Corona sueca',
        'DKK': 'Corona danesa',
        'PLN': 'Zloty polaco',
        'CNY': 'Yuan chino',
    }
    
    # Flags de monedas (emoji)
    currency_flags = {
        'EUR': '🇪🇺',
        'USD': '🇺🇸',
        'GBP': '🇬🇧',
        'GBX': '🇬🇧',
        'JPY': '🇯🇵',
        'CHF': '🇨🇭',
        'AUD': '🇦🇺',
        'CAD': '🇨🇦',
        'HKD': '🇭🇰',
        'SGD': '🇸🇬',
        'NOK': '🇳🇴',
        'SEK': '🇸🇪',
        'DKK': '🇩🇰',
        'PLN': '🇵🇱',
        'CNY': '🇨🇳',
    }
    
    # Preparar datos para la tabla
    currency_rates = []
    for currency, count in user_currencies:
        if currency in all_rates:
            to_eur = all_rates[currency]
            from_eur = 1 / to_eur if to_eur > 0 else 0
            
            currency_rates.append({
                'currency': currency,
                'currency_name': currency_names.get(currency, currency),
                'flag': currency_flags.get(currency, '🌐'),
                'to_eur': to_eur,
                'from_eur': from_eur,
                'asset_count': count
            })
    
    # Ordenar por moneda
    currency_rates.sort(key=lambda x: x['currency'])
    
    return render_template('portfolio/currencies.html', 
                          currency_rates=currency_rates,
                          cache_info=cache_info)


@portfolio_bp.route('/currencies/refresh', methods=['POST'])
@login_required
def currencies_refresh():
    """Fuerza actualización de tasas de cambio"""
    from app.services.currency_service import get_exchange_rates
    
    try:
        # Forzar actualización
        rates = get_exchange_rates(force_refresh=True)
        flash(f'✅ Tasas actualizadas correctamente ({len(rates)} monedas)', 'success')
    except Exception as e:
        flash(f'❌ Error al actualizar tasas: {str(e)}', 'error')
    
    return redirect(url_for('portfolio.currencies'))


@portfolio_bp.route('/holdings')
@login_required
def holdings_list():
    """Lista de posiciones actuales con precios en tiempo real"""
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
    
    # Convertir a lista y calcular valores actuales
    holdings_unified = []
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['asset_id'] = asset_id
        
        # Calcular valor actual y P&L (con conversión EUR)
        asset = data['asset']
        if asset.current_price:
            # Valor en moneda local
            current_value_local = data['total_quantity'] * asset.current_price
            
            # Conversión a EUR
            current_value_eur = convert_to_eur(current_value_local, asset.currency)
            total_cost_eur = convert_to_eur(data['total_cost'], asset.currency)
            
            data['current_value_local'] = current_value_local
            data['current_value_eur'] = current_value_eur
            data['local_currency'] = asset.currency
            data['unrealized_pl_eur'] = current_value_eur - total_cost_eur
            data['unrealized_pl_pct'] = ((current_value_eur / total_cost_eur) - 1) * 100 if total_cost_eur > 0 else 0
        else:
            data['current_value_local'] = None
            data['current_value_eur'] = None
            data['local_currency'] = asset.currency
            data['unrealized_pl_eur'] = None
            data['unrealized_pl_pct'] = None
        
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
    
    # Paginación (100 transacciones por página)
    page = request.args.get('page', 1, type=int)
    per_page = 100
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    transactions = pagination.items
    
    # Obtener todas las cuentas para el selector
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(BrokerAccount.broker_id, BrokerAccount.account_name).all()
    
    return render_template('portfolio/transactions.html', 
                          transactions=transactions,
                          accounts=accounts,
                          filtered=filtered,
                          pagination=pagination)


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
    
    return render_template('portfolio/asset_registry.html',
                          registries=registries,
                          stats=stats,
                          sort_by=current_sort_by,
                          sort_order=current_sort_order)


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
        
        # Invalidar cache de métricas (transacción editada)
        from app.services.metrics.cache import MetricsCacheService
        MetricsCacheService.invalidate(current_user.id)
        
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
                          action='edit',
                          transaction=transaction)


@portfolio_bp.route('/transactions/<int:id>/delete', methods=['POST'])
@login_required
def transaction_delete(id):
    """Eliminar transacción existente"""
    transaction = Transaction.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()
    
    # Guardar cuenta para recalcular holdings después
    account_id = transaction.account_id
    asset_symbol = transaction.asset.symbol if transaction.asset else transaction.transaction_type
    
    # Eliminar transacción
    db.session.delete(transaction)
    db.session.commit()
    
    # Recalcular holdings de la cuenta afectada
    from app.services.importer_v2 import CSVImporterV2
    importer = CSVImporterV2(current_user.id, account_id)
    importer._recalculate_holdings()
    db.session.commit()
    
    # Invalidar cache de métricas
    from app.services.metrics.cache import MetricsCacheService
    MetricsCacheService.invalidate(current_user.id)
    
    flash(f'✅ Transacción de {asset_symbol} eliminada correctamente. Holdings recalculados.', 'success')
    return redirect(url_for('portfolio.transactions_list'))


@portfolio_bp.route('/api/holdings', methods=['GET'])
@login_required
def api_get_holdings():
    """API: Obtener holdings actuales del usuario para auto-selección en SELL"""
    try:
        # Parámetro opcional: filtrar por cuenta
        account_id = request.args.get('account_id', type=int)
        
        # Obtener cuentas del usuario
        user_accounts = BrokerAccount.query.filter_by(user_id=current_user.id).all()
        
        if not user_accounts:
            return jsonify({'success': True, 'holdings': [], 'total': 0, 'accounts': 0, 'message': 'No tienes cuentas de broker'})
        
        # Si se especifica una cuenta, filtrar solo esa
        if account_id:
            account_ids = [account_id] if any(acc.id == account_id for acc in user_accounts) else []
        else:
            account_ids = [acc.id for acc in user_accounts]
        
        if not account_ids:
            return jsonify({'success': True, 'holdings': [], 'total': 0, 'accounts': 0, 'message': 'Cuenta no encontrada'})
        
        # Obtener holdings de esas cuentas con cantidad > 0
        holdings = PortfolioHolding.query.filter(
            PortfolioHolding.account_id.in_(account_ids),
            PortfolioHolding.quantity > 0
        ).all()
        
        result = []
        for h in holdings:
            try:
                # Obtener asset (puede no existir si fue eliminado)
                asset = Asset.query.get(h.asset_id)
                if not asset:
                    continue
                
                # Obtener cuenta para mostrar broker
                account = BrokerAccount.query.get(h.account_id)
                broker_name = account.broker.name if account and account.broker else 'Unknown'
                
                result.append({
                    'id': h.asset_id,
                    'symbol': asset.symbol or 'N/A',
                    'name': asset.name or asset.symbol or 'Sin nombre',
                    'isin': asset.isin or '',
                    'currency': asset.currency or 'USD',
                    'asset_type': asset.asset_type or 'Stock',
                    'exchange': asset.exchange or '',
                    'mic': asset.mic or '',
                    'yahoo_suffix': asset.yahoo_suffix or '',
                    'quantity': float(h.quantity),
                    'avg_buy_price': float(h.average_buy_price) if h.average_buy_price else 0,
                    'current_price': float(asset.current_price) if asset.current_price else (float(h.average_buy_price) if h.average_buy_price else 0),
                    'broker': broker_name,
                    'account_id': h.account_id
                })
            except Exception as e:
                # Si falla un holding individual, continuar con los demás
                print(f"Error procesando holding {h.id}: {str(e)}")
                continue
        
        return jsonify({'success': True, 'holdings': result, 'total': len(result), 'accounts': len(account_ids)})
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERROR EN API HOLDINGS: {error_trace}")
        return jsonify({'success': False, 'error': str(e), 'traceback': error_trace}), 500


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


@portfolio_bp.route('/transactions/new', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Registrar nueva transacción manual"""
    form = ManualTransactionForm()
    
    # Poblar choices dinámicamente con opción "Todas"
    accounts = BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    form.account_id.choices = [('', '-- Todas las cuentas --')] + [
        (acc.id, f'{acc.broker.name} - {acc.account_name}')
        for acc in accounts
    ]
    
    if form.validate_on_submit():
        # Si no se seleccionó cuenta específica y es SELL, requerir selección
        if not form.account_id.data:
            flash('❌ Debes seleccionar una cuenta específica para registrar la transacción', 'error')
            return render_template('portfolio/transaction_form.html', form=form, transaction=None)
        
        account_id = int(form.account_id.data)
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
            account_id=account_id,
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
        db.session.flush()  # Obtener ID de la transacción
        
        # Recalcular holdings usando FIFO (el método correcto)
        from app.services.fifo_calculator import FIFOCalculator
        
        # Obtener todas las transacciones de este asset en esta cuenta
        all_transactions = Transaction.query.filter_by(
            user_id=current_user.id,
            account_id=account_id,
            asset_id=asset.id
        ).order_by(Transaction.transaction_date).all()
        
        # Calcular holding con FIFO
        fifo = FIFOCalculator()
        
        # Procesar todas las transacciones EXCEPTO la actual
        for t in all_transactions:
            if t.id == transaction.id:
                continue  # Saltar la transacción que acabamos de crear
            
            if t.transaction_type == 'BUY':
                fifo.add_buy(
                    quantity=t.quantity,
                    price=t.price,
                    date=t.transaction_date,
                    total_cost=abs(t.amount) + (t.commission or 0) + (t.fees or 0) + (t.tax or 0)
                )
            elif t.transaction_type == 'SELL':
                fifo.add_sell(
                    quantity=t.quantity,
                    date=t.transaction_date
                )
        
        # Ahora procesar la transacción actual
        cost_basis_of_sale = None
        if form.transaction_type.data == 'BUY':
            fifo.add_buy(
                quantity=form.quantity.data,
                price=form.price.data,
                date=form.transaction_date.data,
                total_cost=abs(amount) + form.commission.data + form.fees.data + form.tax.data
            )
        elif form.transaction_type.data == 'SELL':
            # add_sell retorna el coste de las acciones vendidas (base de coste)
            cost_basis_of_sale = fifo.add_sell(
                quantity=form.quantity.data,
                date=form.transaction_date.data
            )
        
        # Obtener o crear holding
        holding = PortfolioHolding.query.filter_by(
            user_id=current_user.id,
            account_id=account_id,
            asset_id=asset.id
        ).first()
        
        current_position = fifo.get_current_position()
        
        if current_position['quantity'] > 0:
            # Hay posición abierta
            if holding:
                holding.quantity = current_position['quantity']
                holding.average_buy_price = current_position['average_buy_price']
                holding.total_cost = current_position['total_cost']
                holding.last_transaction_date = form.transaction_date.data
            else:
                holding = PortfolioHolding(
                    user_id=current_user.id,
                    account_id=account_id,
                    asset_id=asset.id,
                    quantity=current_position['quantity'],
                    average_buy_price=current_position['average_buy_price'],
                    total_cost=current_position['total_cost'],
                    first_purchase_date=form.transaction_date.data,
                    last_transaction_date=form.transaction_date.data
                )
                db.session.add(holding)
        else:
            # Posición cerrada, eliminar holding si existe
            if holding:
                db.session.delete(holding)
        
        # Calcular P&L realizado si es SELL
        if form.transaction_type.data == 'SELL' and cost_basis_of_sale is not None:
            # Revenue = (precio_venta * cantidad) - comisiones - fees - tax
            revenue = abs(amount) - form.commission.data - form.fees.data - form.tax.data
            # P&L = revenue - coste de compra
            realized_pl = revenue - float(cost_basis_of_sale)
            transaction.realized_pl = realized_pl
            
            # Calcular % de ganancia
            if float(cost_basis_of_sale) > 0:
                transaction.realized_pl_pct = (realized_pl / float(cost_basis_of_sale)) * 100
        
        db.session.commit()
        
        # Invalidar cache de métricas (nueva transacción)
        from app.services.metrics.cache import MetricsCacheService
        MetricsCacheService.invalidate(current_user.id)
        
        action_text = 'compra' if form.transaction_type.data == 'BUY' else 'venta'
        flash(f'✅ {form.transaction_type.data} de {form.symbol.data} registrada correctamente', 'success')
        return redirect(url_for('portfolio.holdings_list'))
    
    return render_template('portfolio/transaction_form.html', form=form, transaction=None, action='new', title='Nueva Transacción')


# ==================== METRICS CACHE ====================

@portfolio_bp.route('/cache/invalidate', methods=['POST'])
@login_required
def invalidate_cache():
    """Invalida manualmente el cache de métricas del usuario"""
    from app.services.metrics.cache import MetricsCacheService
    
    was_invalidated = MetricsCacheService.invalidate(current_user.id)
    
    if was_invalidated:
        flash('✅ Cache invalidado. Las métricas se recalcularán en la próxima visita.', 'success')
    else:
        flash('ℹ️ No había cache para invalidar. Las métricas ya se recalcularán.', 'info')
    
    return redirect(url_for('portfolio.dashboard'))


# ==================== CSV IMPORT ====================

def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@portfolio_bp.route('/import')
@login_required
def import_csv():
    """Formulario para subir CSV con auto-detección de broker"""
    # Ya NO es necesario obtener cuentas - se crean automáticamente
    return render_template('portfolio/import_csv.html', title='Importar CSV')


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


def get_or_create_broker_account(user_id, broker_format):
    """
    Obtiene o crea automáticamente la cuenta del broker según el formato CSV detectado
    
    Args:
        user_id: ID del usuario
        broker_format: Formato detectado ('IBKR', 'DEGIRO_TRANSACTIONS', 'DEGIRO_ACCOUNT', etc.)
        
    Returns:
        BrokerAccount: La cuenta existente o recién creada
    """
    # Normalizar formato a nombre de broker
    # DEGIRO_TRANSACTIONS y DEGIRO_ACCOUNT → ambos a "Degiro"
    # IBKR → "IBKR"
    broker_format_lower = broker_format.lower()
    
    if 'degiro' in broker_format_lower:
        broker_search_name = 'DeGiro'
        account_default_name = 'Degiro'
    elif broker_format_lower == 'ibkr':
        broker_search_name = 'IBKR'
        account_default_name = 'IBKR'
    else:
        # Fallback para formatos no reconocidos
        broker_search_name = broker_format.upper()
        account_default_name = broker_format.upper()
    
    # Buscar broker predefinido en la tabla de Brokers
    # Primero intentar buscar por nombre exacto, luego por LIKE
    broker = Broker.query.filter(
        db.func.lower(Broker.name).like(f'%{broker_search_name.lower()}%')
    ).first()
    
    if not broker:
        # Si no existe, crear el broker automáticamente
        # Mapeo de nombres de broker a full_name
        broker_full_names = {
            'IBKR': 'Interactive Brokers',
            'DeGiro': 'DeGiro',
            'Degiro': 'DeGiro'
        }
        full_name = broker_full_names.get(broker_search_name, broker_search_name)
        
        broker = Broker(
            name=broker_search_name,
            full_name=full_name,
            is_active=True
        )
        db.session.add(broker)
        db.session.flush()
        print(f"✅ Broker '{broker_search_name}' creado automáticamente")
    
    # Buscar cuenta existente del usuario para este broker
    account = BrokerAccount.query.filter_by(
        user_id=user_id,
        broker_id=broker.id,
        is_active=True
    ).first()
    
    if not account:
        # Crear cuenta con nombre por defecto
        account = BrokerAccount(
            user_id=user_id,
            broker_id=broker.id,
            account_name=account_default_name,  # "IBKR" o "Degiro"
            account_number=None,  # Campo vacío, solo el usuario puede rellenarlo
            base_currency='EUR',  # Moneda base por defecto
            is_active=True
        )
        db.session.add(account)
        db.session.flush()
        print(f"✅ Cuenta '{account_default_name}' creada automáticamente para usuario {user_id}")
    else:
        print(f"✅ Usando cuenta existente '{account.account_name}' para broker {broker.name}")
    
    db.session.commit()
    return account


@portfolio_bp.route('/import/process', methods=['POST'])
@login_required
def import_csv_process():
    """Procesa uno o múltiples archivos CSV subidos con auto-detección de broker"""
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
            broker_format = parsed_data.get('format', 'unknown')
            print(f"📊 DEBUG: CSV parseado correctamente. Formato: {broker_format}")
            
            # Auto-detectar y obtener/crear cuenta del broker
            print(f"📊 DEBUG: Auto-detectando cuenta del broker para formato: {broker_format}")
            account = get_or_create_broker_account(current_user.id, broker_format)
            print(f"📊 DEBUG: Usando cuenta: {account.account_name} (ID: {account.id})")
            
            # Importar a BD con AssetRegistry (cache global)
            print(f"\n📊 DEBUG: Iniciando importación para archivo: {filename}")
            importer = CSVImporterV2(user_id=current_user.id, broker_account_id=account.id, enable_enrichment=True)
            
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
    
    # Invalidar cache de métricas después de importar (si hubo éxito)
    if total_stats['files_processed'] > 0:
        from app.services.metrics.cache import MetricsCacheService
        MetricsCacheService.invalidate(current_user.id)
        print(f"♻️  DEBUG: Cache de métricas invalidado tras importar {total_stats['files_processed']} archivo(s)")
    
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
            'skipped': total_stats.get('transactions_skipped', 0),
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
        
        # Si es una petición AJAX, devolver JSON con la URL de redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'success': True, 'redirect_url': redirect_url}), 200
        
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
        
        redirect_url = url_for('portfolio.import_csv') + '?' + urlencode(query_params)
        
        # Si es una petición AJAX, devolver JSON con la URL de redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'redirect_url': redirect_url}), 200
        
        return redirect(redirect_url)
    
    flash('❌ No se pudo importar ningún archivo', 'error')
    return redirect(url_for('portfolio.import_csv'))

@portfolio_bp.route('/mappings')
@login_required
def mappings():
    """
    Página de gestión de mapeos (MIC→Yahoo, Exchange→Yahoo, DeGiro→IBKR)
    """
    from app.models import MappingRegistry
    
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
                          countries=countries)


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


# ==================== ASSET DETAILS (Sprint 3 Final) ====================

@portfolio_bp.route('/asset/<int:id>')
@login_required
def asset_detail(id):
    """
    Vista detallada de un asset con todas las métricas de Yahoo Finance
    """
    asset = Asset.query.get_or_404(id)
    
    # Verificar que el usuario tenga alguna posición en este asset
    holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id,
        asset_id=id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    if not holdings:
        flash('❌ No tienes posiciones en este activo', 'error')
        return redirect(url_for('portfolio.dashboard'))
    
    # Calcular totales del usuario para este asset
    total_quantity = sum(h.quantity for h in holdings)
    total_cost = sum(h.total_cost for h in holdings)
    average_buy_price = total_cost / total_quantity if total_quantity > 0 else 0
    
    # P&L en tiempo real
    current_value = None
    unrealized_pl = None
    unrealized_pl_pct = None
    
    if asset.current_price:
        current_value = total_quantity * asset.current_price
        unrealized_pl = current_value - total_cost
        unrealized_pl_pct = (unrealized_pl / total_cost * 100) if total_cost > 0 else 0
    
    # Historial de transacciones del usuario para este asset
    transactions = Transaction.query.filter_by(
        asset_id=id
    ).join(BrokerAccount).filter(
        BrokerAccount.user_id == current_user.id
    ).order_by(Transaction.transaction_date.desc()).limit(10).all()
    
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
        transactions=transactions
    )


# ==================== PRICE UPDATES (Sprint 3 Final) ====================

@portfolio_bp.route('/prices/update', methods=['POST'])
@login_required
def update_prices():
    """
    Inicia actualización de precios en background y devuelve inmediatamente
    """
    from app.services.market_data.services import PriceUpdater
    from flask_wtf.csrf import validate_csrf
    import threading
    
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        return jsonify({'error': 'Token CSRF inválido'}), 400
    
    user_id = current_user.id
    session_key = f'price_update_{user_id}'
    
    # Verificar si ya hay una actualización en progreso
    with price_progress_lock:
        if session_key in price_update_progress_cache:
            existing = price_update_progress_cache[session_key]
            if existing.get('status') == 'running':
                return jsonify({'error': 'Ya hay una actualización en progreso'}), 400
    
    # Inicializar progreso
    with price_progress_lock:
        price_update_progress_cache[session_key] = {
            'status': 'running',
            'current': 0,
            'total': 0,
            'current_asset': 'Iniciando...',
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'start_time': time.time()
        }
    
    # Capturar el contexto de la aplicación para el thread
    from flask import current_app
    app = current_app._get_current_object()
    
    # Función para ejecutar en background con contexto de aplicación
    def run_price_update():
        with app.app_context():
            try:
                updater = PriceUpdater(progress_callback=lambda data: update_price_progress(session_key, data))
                result = updater.update_asset_prices()
                
                # Actualizar con resultado final (aplanar para facilitar acceso en frontend)
                with price_progress_lock:
                    price_update_progress_cache[session_key].update({
                        'status': 'completed',
                        'result': result,
                        'success': result.get('success', 0),
                        'failed': result.get('failed', 0),
                        'skipped': result.get('skipped', 0),
                        'total': result.get('total', 0),
                        'end_time': time.time()
                    })
                
                # Invalidar cache de métricas (precios actualizados)
                from app.services.metrics.cache import MetricsCacheService
                MetricsCacheService.invalidate(user_id)
            except Exception as e:
                import traceback
                with price_progress_lock:
                    price_update_progress_cache[session_key].update({
                        'status': 'error',
                        'error': str(e),
                        'traceback': traceback.format_exc(),
                        'end_time': time.time()
                    })
    
    # Iniciar thread
    thread = threading.Thread(target=run_price_update, daemon=True)
    thread.start()
    
    return jsonify({'status': 'started', 'session_key': session_key})


def update_price_progress(session_key, data):
    """Callback para actualizar el progreso"""
    with price_progress_lock:
        if session_key in price_update_progress_cache:
            price_update_progress_cache[session_key].update(data)


@portfolio_bp.route('/prices/update/progress', methods=['GET'])
@login_required
def price_update_progress():
    """Consulta el progreso de la actualización de precios"""
    user_id = current_user.id
    session_key = f'price_update_{user_id}'
    
    with price_progress_lock:
        progress = price_update_progress_cache.get(session_key, {
            'status': 'not_started',
            'current': 0,
            'total': 0
        })
    
    return jsonify(progress)


# ❌ ENDPOINT ELIMINADO: /asset-registry/sync-to-assets
# La sincronización ahora es AUTOMÁTICA al guardar en AssetRegistry (ver asset_registry_edit)
# No se necesita sincronización manual


# ============================================================================
# PERFORMANCE & CHARTS (Sprint 4 - HITO 3)
# ============================================================================

@portfolio_bp.route('/performance')
@login_required
def performance():
    """
    Página de análisis de performance con gráficos de evolución
    """
    return render_template('portfolio/performance.html')


@portfolio_bp.route('/api/evolution')
@login_required
def api_evolution():
    """
    API endpoint que devuelve datos de evolución del portfolio para Chart.js
    """
    from app.services.metrics.portfolio_evolution import PortfolioEvolutionService
    
    # Obtener frecuencia del query parameter (default: weekly)
    frequency = request.args.get('frequency', 'weekly')
    
    if frequency not in ['daily', 'weekly', 'monthly']:
        frequency = 'weekly'
    
    try:
        evolution_service = PortfolioEvolutionService(current_user.id)
        data = evolution_service.get_evolution_data(frequency=frequency)
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"Error en api_evolution: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

