"""
Rutas del dashboard principal del portfolio
"""
from collections import defaultdict
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app.models import BrokerAccount, Asset, PortfolioHolding, Transaction
from app.services.currency_service import convert_to_eur
from app.services.metrics import BasicMetrics

@portfolio_bp.route('/')
@login_required
def dashboard():
    """Dashboard del portfolio con holdings unificados"""
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
    
    OZ_TROY_TO_G = 31.1035
    for h in holdings_unified:
        asset = h['asset']
        
        # Coste: Commodity (metales) usa transacciones manuales en EUR
        if asset.asset_type == 'Commodity':
            cost_eur = h['total_cost']
        else:
            cost_eur = convert_to_eur(h['total_cost'], asset.currency)
        h['cost_eur'] = cost_eur
        total_cost += cost_eur
        
        if asset and asset.current_price:
            # Commodity: precio Yahoo USD/oz, cantidad en gramos
            if asset.asset_type == 'Commodity':
                oz_from_g = h['total_quantity'] / OZ_TROY_TO_G
                value_usd = oz_from_g * asset.current_price
                current_value_eur = convert_to_eur(value_usd, 'USD')
                h['current_value_local'] = value_usd
                h['local_currency'] = 'USD'
            else:
                current_value_local = h['total_quantity'] * asset.current_price
                h['current_value_local'] = current_value_local
                h['local_currency'] = asset.currency
                current_value_eur = convert_to_eur(current_value_local, asset.currency)
            
            # Calcular P&L individual
            pl_individual = current_value_eur - cost_eur
            h['pl_eur'] = pl_individual  # Guardar para el template
            h['current_value_eur'] = current_value_eur  # Para peso % y template
            
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
            h['current_value_eur'] = cost_eur  # Para peso % y template
    
    # Calcular porcentaje
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0
    
    # Calcular peso % de cada holding
    for h in holdings_unified:
        if 'current_value_eur' in h and total_value > 0:
            h['weight_pct'] = (h['current_value_eur'] / total_value) * 100
        else:
            h['weight_pct'] = 0
    
    # Calcular distribuciones: países, sectores, assets, industrias, brokers, tipos
    country_distribution = defaultdict(float)
    sector_distribution = defaultdict(float)
    asset_distribution = defaultdict(float)
    industry_distribution = defaultdict(float)
    broker_distribution = defaultdict(float)
    asset_type_distribution = defaultdict(float)
    
    for h in holdings_unified:
        asset = h['asset']
        value_eur = h.get('current_value_eur', h.get('cost_eur', 0))
        
        # País
        if asset.country:
            country_distribution[asset.country] += value_eur
        
        # Sector
        if asset.sector:
            sector_distribution[asset.sector] += value_eur
        
        # Asset (Top 10 se filtrará en el template)
        if asset.symbol:
            asset_distribution[asset.symbol] += value_eur
        
        # Industria
        if asset.industry:
            industry_distribution[asset.industry] += value_eur
        
        # Broker (sumar por cada broker único en las cuentas)
        if 'accounts' in h and len(h['accounts']) > 0:
            # Obtener brokers únicos para este holding
            brokers_in_holding = set(acc.get('broker', 'Manual') for acc in h['accounts'])
            # Dividir el valor entre los brokers únicos (un asset puede estar en múltiples brokers)
            value_per_broker = value_eur / len(brokers_in_holding) if len(brokers_in_holding) > 0 else value_eur
            for broker_name in brokers_in_holding:
                broker_distribution[broker_name] += value_per_broker
        
        # Tipo de Asset (ADR se agrupa como Stock)
        asset_type = asset.asset_type if asset.asset_type else 'Stock'
        if asset_type == 'ADR':
            asset_type = 'Stock'  # Agrupar ADR con Stock
        asset_type_distribution[asset_type] += value_eur
    
    # Convertir a listas ordenadas por valor (descendente)
    country_data = sorted(country_distribution.items(), key=lambda x: x[1], reverse=True)
    sector_data = sorted(sector_distribution.items(), key=lambda x: x[1], reverse=True)
    asset_data_sorted = sorted(asset_distribution.items(), key=lambda x: x[1], reverse=True)
    industry_data = sorted(industry_distribution.items(), key=lambda x: x[1], reverse=True)
    broker_data = sorted(broker_distribution.items(), key=lambda x: x[1], reverse=True)
    asset_type_data = sorted(asset_type_distribution.items(), key=lambda x: x[1], reverse=True)
    
    # Assets: Top 10 + "Otros"
    asset_data_top10 = asset_data_sorted[:10]
    asset_data_others = asset_data_sorted[10:]
    others_total = sum(value for _, value in asset_data_others)
    if others_total > 0:
        asset_data_top10.append(('Otros', others_total))
    asset_data = asset_data_top10
    
    # Calcular métricas básicas (Sprint 4 - HITO 1 + Cache)
    from app.services.metrics.cache import MetricsCacheService
    from app.services.metrics.stocks_etf_metrics import StocksEtfMetrics
    
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

    # Apalancamiento: excluir crypto (Revolut X no incluye depósitos/retiradas en CSV)
    # Usar métricas Stock+ETF solo para Dinero Prestado y desglose
    leverage_cost = total_cost  # fallback por defecto
    holdings_stock_etf = [h for h in holdings_unified if h.get('asset') and (h['asset'].asset_type or '').strip() in ('Stock', 'ETF')]
    if holdings_stock_etf:
        total_value_stock_etf = sum(h.get('current_value_eur', h.get('cost_eur', 0)) for h in holdings_stock_etf)
        total_cost_stock_etf = sum(h.get('cost_eur', 0) for h in holdings_stock_etf)
        pl_unrealized_stock_etf = total_value_stock_etf - total_cost_stock_etf
        metrics_stock_etf = StocksEtfMetrics.get_all_metrics(
            current_user.id, total_value_stock_etf, total_cost_stock_etf, pl_unrealized_stock_etf
        )
        metrics['leverage'] = metrics_stock_etf['leverage']
        metrics['total_account'] = metrics_stock_etf['total_account']
        leverage_cost = total_cost_stock_etf
    else:
        # Solo crypto: no se puede calcular apalancamiento (sin depósitos en CSV Revolut)
        metrics['leverage'] = {'broker_money': 0.0, 'user_money': 0.0, 'leverage_ratio': 0.0,
                              'total_deposits': 0.0, 'total_withdrawals': 0.0, 'pl_realized': 0.0,
                              'pl_unrealized': 0.0, 'total_dividends': 0.0, 'total_fees': 0.0}
        metrics['total_account'] = {'total_account_value': 0.0, 'deposits': 0.0, 'withdrawals': 0.0,
                                   'pl_realized': 0.0, 'pl_unrealized': 0.0, 'dividends': 0.0, 'fees': 0.0,
                                   'cash': 0.0, 'leverage': 0.0}
        leverage_cost = 0.0
    
    # Calcular rentabilidades año a año
    from app.services.metrics.modified_dietz import ModifiedDietzCalculator
    yearly_returns = ModifiedDietzCalculator.get_yearly_returns(current_user.id)
    
    # Calcular métricas de dividendos
    from app.services.metrics.dividend_metrics import DividendMetrics
    monthly_dividends = DividendMetrics.get_monthly_dividends_last_12_months(current_user.id)
    annualized_dividends = DividendMetrics.get_annualized_dividends_ytd(current_user.id)
    yearly_dividends = DividendMetrics.get_yearly_dividends_from_start(current_user.id)
    
    # Calcular comparación con benchmarks (rentabilidades anualizadas)
    from app.services.metrics.benchmark_comparison import BenchmarkComparisonService
    benchmark_comparison = BenchmarkComparisonService(current_user.id)
    benchmark_annualized = benchmark_comparison.get_annualized_returns_summary()
    
    return render_template(
        'portfolio/dashboard.html',
        accounts=accounts,
        holdings=holdings_unified,
        total_value=total_value,
        total_cost=total_cost,
        total_pl=total_pl,
        total_pl_pct=total_pl_pct,
        leverage_cost=leverage_cost,  # Stock+ETF solo (apalancamiento excluye crypto)
        last_price_update=last_price_update,
        last_sync=last_sync,
        unified=True,  # Flag para indicar que son holdings unificados
        metrics=metrics,
        country_distribution=country_data,
        sector_distribution=sector_data,
        asset_distribution=asset_data,
        industry_distribution=industry_data,
        broker_distribution=broker_data,
        asset_type_distribution=asset_type_data,
        yearly_returns=yearly_returns,
        monthly_dividends=monthly_dividends,
        annualized_dividends=annualized_dividends,
        yearly_dividends=yearly_dividends,
        benchmark_annualized=benchmark_annualized
    )


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

