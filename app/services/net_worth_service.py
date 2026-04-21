"""
Servicio de Patrimonio Neto (Net Worth)
Calcula el patrimonio total, desglose por tipo de activo, evolución histórica y proyecciones.
"""
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

from sqlalchemy.exc import OperationalError

from app import db
from app.models.portfolio import PortfolioHolding
from app.models.asset import Asset
from app.models.user import User
from app.services.bank_service import BankService
from app.services.crypto_metrics import compute_crypto_metrics
from app.services.metales_metrics import compute_metales_metrics
from app.services.stocks_metrics import compute_stocks_metrics
from app.services.debt_service import DebtService
from app.services.currency_service import convert_to_eur
from app.services.currency_service import get_exchange_rates
from app.services.metrics.pnl_lib import create_portfolio_snapshot


def get_cash_total(user_id: int, year: int = None, month: int = None) -> float:
    """Total de cash en bancos para un mes dado (o actual)."""
    if year is None or month is None:
        today = date.today()
        year, month = today.year, today.month
    return BankService.get_total_cash_by_month(user_id, year, month) or 0.0


def get_portfolio_value(user_id: int) -> float:
    """Valor actual del portfolio (Stock + ETF)."""
    metrics = compute_stocks_metrics(user_id)
    return metrics['total_value']


def get_crypto_value(user_id: int) -> float:
    """Valor actual de cryptomonedas."""
    metrics = compute_crypto_metrics(user_id)
    return metrics.get('total_value', 0.0)


def get_metales_value(user_id: int) -> float:
    """Valor actual de metales preciosos."""
    metrics = compute_metales_metrics(user_id)
    return metrics.get('total_value', 0.0)


def get_real_estate_value(user_id: int) -> float:
    """Valor total estimado de inmuebles (última tasación o precio compra)."""
    try:
        from app.models import RealEstateProperty
        props = RealEstateProperty.query.filter_by(user_id=user_id).all()
        return sum(p.get_estimated_value() for p in props)
    except OperationalError:
        return 0.0


def _get_real_estate_value_at_date(user_id: int, target_date) -> float:
    """Valor de inmuebles en una fecha: propiedades compradas antes de la fecha, última tasación hasta ese año."""
    try:
        from app.models import RealEstateProperty, PropertyValuation
        today = target_date.date() if hasattr(target_date, 'date') else target_date
        props = RealEstateProperty.query.filter(
            RealEstateProperty.user_id == user_id,
            RealEstateProperty.purchase_date <= today
        ).all()
        total = 0.0
        for p in props:
            last_val = PropertyValuation.query.filter(
                PropertyValuation.property_id == p.id,
                PropertyValuation.year <= today.year
            ).order_by(PropertyValuation.year.desc()).first()
            total += last_val.value if last_val else p.purchase_price
        return total
    except OperationalError:
        return 0.0


def get_debt_total(user_id: int) -> float:
    """Deuda total pendiente."""
    return DebtService.get_total_debt_remaining(user_id) or 0.0


def _convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
    """
    Convierte entre monedas usando tasas a EUR.
    get_exchange_rates() retorna tasas a EUR: 1 unidad de currency = rate[currency] EUR.
    """
    if amount is None:
        return 0.0
    fc = (from_currency or "EUR").upper()
    tc = (to_currency or "EUR").upper()
    if fc == tc:
        return float(amount)
    # 1) from -> EUR
    eur = convert_to_eur(amount, fc)
    if tc == "EUR":
        return float(eur)
    # 2) EUR -> to
    rates = get_exchange_rates()
    rate_to = rates.get(tc) or 1.0
    return float(eur) / float(rate_to) if rate_to else float(eur)


def get_commodities_snapshot(user_id: int) -> List[Dict[str, Any]]:
    """
    Snapshot ligero para widget 'Commodities' en dashboard.
    Devuelve 3 filas: Oro, Plata, Oil Brent, con precio en USD y % cambio día.
    """
    # tickers Yahoo (Chart API). En nuestro modelo es Asset.symbol (yahoo_suffix vacío).
    wanted = [
        {"symbol": "GC=F", "name": "Oro", "currency": "USD"},
        {"symbol": "SI=F", "name": "Plata", "currency": "USD"},
        {"symbol": "BZ=F", "name": "Oil Brent", "currency": "USD"},
    ]

    rows: List[Dict[str, Any]] = []
    for spec in wanted:
        sym = spec["symbol"]
        a = Asset.query.filter_by(symbol=sym).first()
        if not a:
            a = Asset(
                symbol=sym,
                name=spec["name"],
                asset_type="Commodity",
                currency=spec["currency"],
                yahoo_suffix="",
            )
            db.session.add(a)
            db.session.flush()

        # Precio en USD para mostrar
        price = a.current_price or 0.0
        price_usd = _convert_amount(price, a.currency, "USD") if price else 0.0

        rows.append(
            {
                "asset_id": a.id,
                "symbol": a.symbol,
                "name": spec["name"],
                "price": price_usd,
                "currency": "USD",
                "day_change_percent": a.day_change_percent,
            }
        )

    # no commit aquí: el dashboard puede llamarse en contextos read-only; el flush ya asignó id
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return rows


def get_net_worth_breakdown(user_id: int) -> Dict[str, Any]:
    """
    Desglose completo del patrimonio neto.
    - Portfolio: valor real del broker (dinero del usuario, sin apalancamiento)
    - Crypto/Metales: valor directo de holdings
    - Patrimonio = Cash + Portfolio + Crypto + Metales (sin restar deudas)
    """
    cash = get_cash_total(user_id)
    
    # Portfolio: usar valor real del broker (considera apalancamiento)
    broker_data = _get_broker_value_at_date(user_id, datetime.now(), use_current_prices=True)
    portfolio = broker_data['total_value']  # Dinero real del usuario en el broker
    
    # Crypto y Metales: valor directo (no tienen apalancamiento)
    crypto = _get_holdings_value_at_date(user_id, datetime.now(), ['Crypto'], use_current_prices=True)
    metales = _get_holdings_value_at_date(user_id, datetime.now(), ['Commodity'], use_current_prices=True)
    real_estate = get_real_estate_value(user_id)

    debt = get_debt_total(user_id)

    # Patrimonio = Cash + Portfolio + Crypto + Metales + Inmuebles (sin restar deudas)
    assets_total = cash + portfolio + crypto + metales + real_estate
    net_worth = assets_total  # No restamos deuda
    
    return {
        'cash': round(cash, 2),
        'portfolio': round(portfolio, 2),  # Valor real del broker
        'crypto': round(crypto, 2),
        'metales': round(metales, 2),
        'real_estate': round(real_estate, 2),
        'assets_total': round(assets_total, 2),
        'debt': round(debt, 2),  # Informativo
        'net_worth': round(net_worth, 2),
        'breakdown_pct': {
            'cash': round(cash / assets_total * 100, 1) if assets_total > 0 else 0,
            'portfolio': round(portfolio / assets_total * 100, 1) if assets_total > 0 else 0,
            'crypto': round(crypto / assets_total * 100, 1) if assets_total > 0 else 0,
            'metales': round(metales / assets_total * 100, 1) if assets_total > 0 else 0,
            'real_estate': round(real_estate / assets_total * 100, 1) if assets_total > 0 else 0,
        }
    }


def get_total_net_worth(user_id: int) -> float:
    """Patrimonio neto total (activos - deudas)."""
    breakdown = get_net_worth_breakdown(user_id)
    return breakdown['net_worth']


def get_net_worth_history(user_id: int, months: int = 12) -> List[Dict[str, Any]]:
    """
    Histórico de patrimonio neto por mes con desglose por tipo de activo.
    - Broker (acciones): usa apalancamiento, se calcula el valor real
    - Crypto y Metales: no tienen apalancamiento, valor directo de holdings
    - Patrimonio = Cash + Broker + Crypto + Metales (sin restar deudas)
    """
    today = date.today()
    history = []
    debt = get_debt_total(user_id)
    
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        year, month = d.year, d.month
        is_current_month = (year == today.year and month == today.month)
        
        # Fecha final del mes (o hoy si es el mes actual)
        if is_current_month:
            target_date = datetime.now()
        else:
            # Último día del mes
            next_month = d + relativedelta(months=1)
            target_date = datetime(next_month.year, next_month.month, 1) - relativedelta(days=1)
            target_date = datetime.combine(target_date.date(), datetime.max.time())
        
        # Cash histórico de bancos externos
        cash = get_cash_total(user_id, year, month)
        
        # Broker (solo acciones) - tiene apalancamiento, calcular valor real
        broker_data = _get_broker_value_at_date(user_id, target_date, is_current_month)
        broker_total = broker_data['total_value']  # Valor real considerando apalancamiento
        
        # Crypto y Metales - NO tienen apalancamiento, valor directo de holdings
        crypto = _get_holdings_value_at_date(user_id, target_date, ['Crypto'], is_current_month)
        metales = _get_holdings_value_at_date(user_id, target_date, ['Commodity'], is_current_month)
        real_estate = _get_real_estate_value_at_date(user_id, target_date)

        # Patrimonio = Cash + Broker + Crypto + Metales + Inmuebles (dinero real del usuario)
        net_worth = cash + broker_total + crypto + metales + real_estate
        
        history.append({
            'year': year,
            'month': month,
            'month_label': d.strftime('%b %Y'),
            'cash': round(cash, 2),  # Cash en bancos externos
            'broker_total': round(broker_total, 2),  # Valor real broker (acciones con apalancamiento)
            'crypto': round(crypto, 2),  # Valor directo crypto (sin apalancamiento)
            'metales': round(metales, 2),  # Valor directo metales (sin apalancamiento)
            'real_estate': round(real_estate, 2),  # Inmuebles (última tasación o precio compra)
            'investments': round(broker_total + crypto + metales + real_estate, 2),
            'debt': round(debt, 2),  # Deuda (informativo, no se resta)
            'net_worth': round(net_worth, 2)
        })
    
    return history


def _get_broker_value_at_date(
    user_id: int,
    target_date,
    use_current_prices: bool = False,
    price_source: str = "current",
) -> Dict[str, float]:
    """
    Calcula el valor real del broker (solo acciones: Stock, ETF, ADR) en una fecha.
    Considera el apalancamiento (cash_balance puede ser negativo).
    """
    from app.models.transaction import Transaction
    from app.services.fifo_calculator import FIFOCalculator
    
    STOCK_TYPES = ['Stock', 'ETF', 'ADR']
    
    # Obtener transacciones hasta la fecha
    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date <= target_date
    ).order_by(Transaction.transaction_date, Transaction.id).all()
    
    fifo_calculators = {}
    cash_balance = 0.0
    
    for txn in transactions:
        asset_id = txn.asset_id if txn.asset_id else None
        
        # Solo procesar transacciones relacionadas con acciones o cash del broker
        asset = txn.asset if asset_id else None
        is_stock_txn = asset and asset.asset_type in STOCK_TYPES
        
        # DEPOSIT: Añade cash al broker
        if txn.transaction_type == 'DEPOSIT':
            amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
            cash_balance += amount_eur
        
        # WITHDRAWAL: Quita cash del broker
        elif txn.transaction_type == 'WITHDRAWAL':
            amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
            cash_balance -= amount_eur
        
        # BUY acciones: quita cash, añade holding
        elif txn.transaction_type == 'BUY' and is_stock_txn:
            total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
            cost_eur = convert_to_eur(total_cost, txn.currency)
            cash_balance -= cost_eur
            
            if asset_id not in fifo_calculators:
                fifo_calculators[asset_id] = {
                    'fifo': FIFOCalculator(symbol=asset.symbol),
                    'asset': asset
                }
            fifo_calculators[asset_id]['fifo'].add_buy(
                quantity=txn.quantity,
                price=txn.price,
                date=txn.transaction_date,
                total_cost=total_cost
            )
        
        # SELL acciones: añade cash, quita holding
        elif txn.transaction_type == 'SELL' and is_stock_txn:
            proceeds = (txn.quantity * txn.price) - txn.commission - txn.fees - txn.tax
            proceeds_eur = convert_to_eur(proceeds, txn.currency)
            cash_balance += proceeds_eur
            
            if asset_id in fifo_calculators:
                fifo_calculators[asset_id]['fifo'].add_sell(
                    quantity=txn.quantity,
                    date=txn.transaction_date
                )
        
        # DIVIDEND: Añade cash
        elif txn.transaction_type == 'DIVIDEND':
            dividend_eur = convert_to_eur(abs(txn.amount), txn.currency)
            cash_balance += dividend_eur
        
        # FEE: Quita cash
        elif txn.transaction_type == 'FEE':
            fee_eur = convert_to_eur(abs(txn.amount), txn.currency)
            cash_balance -= fee_eur
    
    # Calcular valor de holdings de acciones
    holdings_value = 0.0
    today = date.today()
    is_today = (target_date.date() >= today) if hasattr(target_date, 'date') else (target_date >= today)
    
    for asset_id, data in fifo_calculators.items():
        fifo = data['fifo']
        asset = data['asset']
        position = fifo.get_current_position()
        current_quantity = position['quantity']
        
        if current_quantity <= 0:
            continue
        
        if use_current_prices and is_today:
            if price_source == "previous_close" and asset.previous_close:
                price = asset.previous_close
            else:
                price = asset.current_price or position['average_buy_price']
        else:
            price = position['average_buy_price']
        
        value_local = current_quantity * price
        value_eur = convert_to_eur(value_local, asset.currency)
        holdings_value += value_eur
    
    # Valor total del broker = cash + holdings
    total_value = cash_balance + holdings_value
    
    return {
        'total_value': total_value,
        'cash_balance': cash_balance,
        'holdings_value': holdings_value
    }


def _get_holdings_value_at_date(
    user_id: int,
    target_date,
    asset_types: List[str],
    use_current_prices: bool = False,
    price_source: str = "current",
) -> float:
    """
    Calcula el valor directo de holdings de ciertos tipos de asset.
    NO considera apalancamiento - valor directo de las posiciones.
    """
    from app.models.transaction import Transaction
    from app.services.fifo_calculator import FIFOCalculator
    
    OZ_TROY_TO_G = 31.1035
    
    # Obtener transacciones hasta la fecha
    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date <= target_date
    ).order_by(Transaction.transaction_date, Transaction.id).all()
    
    fifo_calculators = {}
    
    for txn in transactions:
        asset_id = txn.asset_id
        if not asset_id:
            continue
        
        asset = txn.asset
        if not asset or asset.asset_type not in asset_types:
            continue
        
        if asset_id not in fifo_calculators:
            fifo_calculators[asset_id] = {
                'fifo': FIFOCalculator(symbol=asset.symbol),
                'asset': asset
            }
        
        if txn.transaction_type == 'BUY':
            total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
            fifo_calculators[asset_id]['fifo'].add_buy(
                quantity=txn.quantity,
                price=txn.price,
                date=txn.transaction_date,
                total_cost=total_cost
            )
        elif txn.transaction_type == 'SELL':
            fifo_calculators[asset_id]['fifo'].add_sell(
                quantity=txn.quantity,
                date=txn.transaction_date
            )
    
    # Calcular valor total
    total_value = 0.0
    today = date.today()
    is_today = (target_date.date() >= today) if hasattr(target_date, 'date') else (target_date >= today)
    
    for asset_id, data in fifo_calculators.items():
        fifo = data['fifo']
        asset = data['asset']
        position = fifo.get_current_position()
        current_quantity = position['quantity']
        
        if current_quantity <= 0:
            continue
        
        if use_current_prices and is_today:
            if price_source == "previous_close" and asset.previous_close:
                price = asset.previous_close
            else:
                price = asset.current_price
            if asset.asset_type == 'Commodity':
                oz_from_g = current_quantity / OZ_TROY_TO_G
                value_local = oz_from_g * price
                value_eur = convert_to_eur(value_local, 'USD')
            else:
                value_local = current_quantity * price
                value_eur = convert_to_eur(value_local, asset.currency)
        else:
            price = position['average_buy_price']
            if asset.asset_type == 'Commodity':
                value_eur = current_quantity * price
            else:
                value_local = current_quantity * price
                value_eur = convert_to_eur(value_local, asset.currency)
        
        total_value += value_eur
    
    return total_value


def _user_has_module(user_id: int, key: str) -> bool:
    """
    Back-end equivalente al filtro user_has_module.
    Si enabled_modules es None, consideramos todos activos.
    """
    u = User.query.get(user_id)
    if not u:
        return True
    return u.has_module(key)


def _has_active_holdings(user_id: int, asset_types: List[str]) -> bool:
    """
    True si hay holdings abiertos (quantity > 0) para alguno de los asset_types.
    """
    return (
        db.session.query(PortfolioHolding.id)
        .join(Asset, PortfolioHolding.asset_id == Asset.id)
        .filter(
            PortfolioHolding.user_id == user_id,
            PortfolioHolding.quantity > 0,
            Asset.asset_type.in_(asset_types),
        )
        .first()
        is not None
    )


def _float_or(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _price_for_previous_close(asset: Asset, current_px: float) -> float:
    """previous_close del activo si existe; si no, current (sin contribución al cambio del día)."""
    pc = getattr(asset, "previous_close", None)
    if pc is None:
        return current_px
    v = _float_or(pc, current_px)
    return current_px if v <= 0 else v


def _broker_equity_now_prev_from_holdings(user_id: int, when: datetime) -> Tuple[float, float]:
    """
    Equity del broker hoy: mismo cash_balance (FIFO/transacciones) que el resto del patrimonio,
    pero valor de posiciones desde PortfolioHolding y precios actual / cierre previo.
    Evita deltas diarios irreales cuando FIFO y holdings visibles no coinciden.
    """
    snap = _get_broker_value_at_date(
        user_id, when, use_current_prices=True, price_source="current"
    )
    cash = _float_or(snap.get("cash_balance"), 0.0)

    holdings_now = 0.0
    holdings_prev = 0.0
    rows = (
        PortfolioHolding.query.filter_by(user_id=user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(Asset)
        .filter(Asset.asset_type.in_(["Stock", "ETF", "ADR"]))
        .all()
    )
    for h in rows:
        asset = h.asset
        if not asset:
            continue
        qty = _float_or(h.quantity, 0.0)
        if qty <= 0:
            continue
        cur_px = h.current_price if h.current_price is not None else asset.current_price
        cur_px = _float_or(cur_px, 0.0)
        prev_px = _price_for_previous_close(asset, cur_px)
        currency = asset.currency or "EUR"
        holdings_now += convert_to_eur(qty * cur_px, currency)
        holdings_prev += convert_to_eur(qty * prev_px, currency)

    return cash + holdings_now, cash + holdings_prev


def _crypto_bucket_now_prev_from_holdings(user_id: int) -> Tuple[float, float]:
    now_v = 0.0
    prev_v = 0.0
    rows = (
        PortfolioHolding.query.filter_by(user_id=user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(Asset)
        .filter(Asset.asset_type == "Crypto")
        .all()
    )
    for h in rows:
        asset = h.asset
        if not asset:
            continue
        qty = _float_or(h.quantity, 0.0)
        if qty <= 0:
            continue
        cur_px = _float_or(h.current_price or asset.current_price, 0.0)
        prev_px = _price_for_previous_close(asset, cur_px)
        currency = asset.currency or "EUR"
        now_v += convert_to_eur(qty * cur_px, currency)
        prev_v += convert_to_eur(qty * prev_px, currency)
    return now_v, prev_v


def _metales_bucket_now_prev_from_holdings(user_id: int) -> Tuple[float, float]:
    """Cantidades en gramos; precios Yahoo en USD/oz troy (igual que metales_metrics)."""
    oz_troy_to_g = 31.1035
    now_v = 0.0
    prev_v = 0.0
    rows = (
        PortfolioHolding.query.filter_by(user_id=user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(Asset)
        .filter(Asset.asset_type == "Commodity")
        .all()
    )
    for h in rows:
        asset = h.asset
        if not asset:
            continue
        qty_g = _float_or(h.quantity, 0.0)
        if qty_g <= 0:
            continue
        px_usd_now = _float_or(h.current_price or asset.current_price, 0.0)
        px_usd_prev = _price_for_previous_close(asset, px_usd_now)
        oz = qty_g / oz_troy_to_g
        now_v += convert_to_eur(oz * px_usd_now, "USD")
        prev_v += convert_to_eur(oz * px_usd_prev, "USD")
    return now_v, prev_v


def get_investments_day_change(user_id: int) -> Optional[Tuple[float, float]]:
    """
    Variación diaria agregada (misma base para % y EUR):
      - Cuenta de acciones: cash del broker (FIFO, apalancamiento) + valor en EUR de
        Stock/ETF/ADR según PortfolioHolding (precio actual vs previous_close).
      - Cripto y metales: mismas reglas sobre PortfolioHolding (alineado con lo que ves en módulos).

    Si falta previous_close en un activo, se usa el precio actual en ambas patas (0 de cambio ese día).

    day_eur = (suma valor ahora) − (suma valor a cierre previo) en esos tres bloques.
    """
    include_stocks = _user_has_module(user_id, "stock") and _has_active_holdings(
        user_id, ["Stock", "ETF", "ADR"]
    )
    include_crypto = _user_has_module(user_id, "crypto") and _has_active_holdings(
        user_id, ["Crypto"]
    )
    include_metales = _user_has_module(user_id, "metales") and _has_active_holdings(
        user_id, ["Commodity"]
    )

    if not (include_stocks or include_crypto or include_metales):
        return None

    now = datetime.now()

    invest_now = 0.0
    invest_prev = 0.0

    if include_stocks:
        broker_now, broker_prev = _broker_equity_now_prev_from_holdings(user_id, now)
        invest_now += broker_now
        invest_prev += broker_prev

    if include_crypto:
        crypto_now, crypto_prev = _crypto_bucket_now_prev_from_holdings(user_id)
        invest_now += crypto_now
        invest_prev += crypto_prev

    if include_metales:
        metales_now, metales_prev = _metales_bucket_now_prev_from_holdings(user_id)
        invest_now += metales_now
        invest_prev += metales_prev

    if invest_prev <= 0:
        return None

    day_eur = round(invest_now - invest_prev, 2)
    day_pct = round((invest_now - invest_prev) / invest_prev * 100.0, 2)
    return (day_pct, day_eur)


def get_investments_day_change_pct(user_id: int) -> Optional[float]:
    """Compatibilidad: solo el porcentaje DAY (misma definición que get_investments_day_change)."""
    pair = get_investments_day_change(user_id)
    return pair[0] if pair else None


def _get_holdings_breakdown_at_date(user_id: int, target_date, use_current_prices: bool = False) -> Dict[str, float]:
    """
    Calcula el valor de holdings por tipo de asset en una fecha específica.
    Solo para mostrar desglose visual, no para calcular patrimonio real.
    """
    from app.models.transaction import Transaction
    from app.services.fifo_calculator import FIFOCalculator
    
    OZ_TROY_TO_G = 31.1035
    
    # Mapeo de asset_type a categoría
    type_mapping = {
        'Stock': 'portfolio',
        'ETF': 'portfolio', 
        'ADR': 'portfolio',
        'Crypto': 'crypto',
        'Commodity': 'metales'
    }
    
    # Obtener transacciones hasta la fecha
    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date <= target_date
    ).order_by(Transaction.transaction_date, Transaction.id).all()
    
    # Reconstruir FIFO por asset
    fifo_calculators = {}
    
    for txn in transactions:
        asset_id = txn.asset_id
        if not asset_id:
            continue
        
        asset = txn.asset
        if not asset or asset.asset_type not in type_mapping:
            continue
        
        if asset_id not in fifo_calculators:
            fifo_calculators[asset_id] = {
                'fifo': FIFOCalculator(symbol=asset.symbol),
                'asset': asset,
                'category': type_mapping[asset.asset_type]
            }
        
        if txn.transaction_type == 'BUY':
            total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
            fifo_calculators[asset_id]['fifo'].add_buy(
                quantity=txn.quantity,
                price=txn.price,
                date=txn.transaction_date,
                total_cost=total_cost
            )
        elif txn.transaction_type == 'SELL':
            fifo_calculators[asset_id]['fifo'].add_sell(
                quantity=txn.quantity,
                date=txn.transaction_date
            )
    
    # Calcular valor por categoría
    totals = {'portfolio': 0.0, 'crypto': 0.0, 'metales': 0.0}
    today = date.today()
    is_today = (target_date.date() >= today) if hasattr(target_date, 'date') else (target_date >= today)
    
    for asset_id, data in fifo_calculators.items():
        fifo = data['fifo']
        asset = data['asset']
        category = data['category']
        position = fifo.get_current_position()
        current_quantity = position['quantity']
        
        if current_quantity <= 0:
            continue
        
        # Decidir qué precio usar
        if use_current_prices and is_today and asset.current_price:
            price = asset.current_price
            if asset.asset_type == 'Commodity':
                oz_from_g = current_quantity / OZ_TROY_TO_G
                value_local = oz_from_g * price
                value_eur = convert_to_eur(value_local, 'USD')
            else:
                value_local = current_quantity * price
                value_eur = convert_to_eur(value_local, asset.currency)
        else:
            price = position['average_buy_price']
            if asset.asset_type == 'Commodity':
                value_eur = current_quantity * price
            else:
                value_local = current_quantity * price
                value_eur = convert_to_eur(value_local, asset.currency)
        
        totals[category] += value_eur
    
    return totals


def get_full_net_worth_history(user_id: int) -> Dict[str, Any]:
    """
    Histórico completo de patrimonio desde el primer registro.
    Devuelve datos y metadatos sobre el rango disponible.
    """
    from app.models import BankBalance, Income, Expense, Transaction
    from datetime import datetime
    
    def to_date(d):
        """Convierte datetime o date a date."""
        if d is None:
            return None
        if isinstance(d, datetime):
            return d.date()
        return d
    
    # Encontrar la fecha más antigua con datos en todas las tablas relevantes
    dates = []
    
    # BankBalance
    oldest_balance = BankBalance.query.filter_by(user_id=user_id).order_by(
        BankBalance.year.asc(), BankBalance.month.asc()
    ).first()
    if oldest_balance:
        dates.append(date(oldest_balance.year, oldest_balance.month, 1))
    
    # Income
    oldest_income = Income.query.filter_by(user_id=user_id).order_by(Income.date.asc()).first()
    if oldest_income and oldest_income.date:
        dates.append(to_date(oldest_income.date))
    
    # Expense
    oldest_expense = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.asc()).first()
    if oldest_expense and oldest_expense.date:
        dates.append(to_date(oldest_expense.date))
    
    # Transaction (operaciones de broker)
    oldest_transaction = Transaction.query.filter_by(user_id=user_id).order_by(
        Transaction.transaction_date.asc()
    ).first()
    if oldest_transaction and oldest_transaction.transaction_date:
        dates.append(to_date(oldest_transaction.transaction_date))
    
    if not dates:
        return {
            'history': get_net_worth_history(user_id, 12),
            'total_months': 12,
            'start_date': None,
            'years_available': 1
        }
    
    oldest_date = min(dates)
    today = date.today()
    
    # Calcular meses desde el inicio
    total_months = (today.year - oldest_date.year) * 12 + (today.month - oldest_date.month) + 1
    years_available = total_months / 12
    # Para el filtro "Todo" del dashboard necesitamos el histórico completo.
    # Si el cálculo se vuelve lento con historiales muy largos, optimizar get_net_worth_history
    # o mover el cálculo completo a una caché dedicada; pero no recortar aquí.
    history = get_net_worth_history(user_id, total_months)
    
    return {
        'history': history,
        'total_months': total_months,
        'start_date': oldest_date.strftime('%Y-%m-%d'),
        'start_label': oldest_date.strftime('%b %Y'),
        'years_available': round(years_available, 1)
    }


def get_net_worth_projection(user_id: int, years: List[int] = [1, 3, 5]) -> Dict[str, Any]:
    """
    Proyección del patrimonio neto basada en tendencia histórica.
    Usa regresión lineal sobre el histórico de cash + tasa de ahorro.
    """
    from app.services.income_expense_aggregator import (
        get_income_monthly_totals_with_adjustment,
        get_expense_monthly_totals_with_adjustment,
    )
    
    # Obtener ingresos y gastos mensuales (últimos 12 meses)
    income_totals = get_income_monthly_totals_with_adjustment(user_id, months=12)
    expense_totals = get_expense_monthly_totals_with_adjustment(user_id, months=12)
    
    # Calcular ahorro mensual promedio
    monthly_savings = []
    for inc, exp in zip(income_totals, expense_totals):
        savings = inc.get('total', 0) - exp.get('total', 0)
        monthly_savings.append(savings)
    
    avg_monthly_savings = np.mean(monthly_savings) if monthly_savings else 0
    
    # Patrimonio actual
    current_net_worth = get_total_net_worth(user_id)
    
    # Proyecciones por año
    projections = {}
    for y in years:
        months_ahead = y * 12
        projected = current_net_worth + (avg_monthly_savings * months_ahead)
        projections[f'{y}y'] = {
            'years': y,
            'projected_value': round(projected, 2),
            'growth': round(projected - current_net_worth, 2),
            'growth_pct': round((projected / current_net_worth - 1) * 100, 1) if current_net_worth > 0 else 0
        }
    
    # Proyección mensual para gráfico (10 años = 120 meses)
    today = date.today()
    projection_chart = []
    for m in range(0, 121, 3):  # Cada 3 meses para no sobrecargar
        future_date = today + relativedelta(months=m)
        projected_value = current_net_worth + (avg_monthly_savings * m)
        projection_chart.append({
            'month': m,
            'year': m // 12,
            'label': future_date.strftime('%b %Y') if m % 12 == 0 else '',
            'value': round(projected_value, 2)
        })
    
    return {
        'current': round(current_net_worth, 2),
        'avg_monthly_savings': round(avg_monthly_savings, 2),
        'projections': projections,
        'projection_chart': projection_chart
    }


def get_savings_rate(user_id: int, months: int = 12) -> Dict[str, Any]:
    """Calcula la tasa de ahorro (ingresos - gastos) / ingresos."""
    from app.services.income_expense_aggregator import (
        get_income_monthly_totals_with_adjustment,
        get_expense_monthly_totals_with_adjustment,
    )
    
    income_totals = get_income_monthly_totals_with_adjustment(user_id, months=months)
    expense_totals = get_expense_monthly_totals_with_adjustment(user_id, months=months)
    
    total_income = sum(i.get('total', 0) for i in income_totals)
    total_expense = sum(e.get('total', 0) for e in expense_totals)
    total_savings = total_income - total_expense
    
    savings_rate = (total_savings / total_income * 100) if total_income > 0 else 0
    
    return {
        'total_income': round(total_income, 2),
        'total_expense': round(total_expense, 2),
        'total_savings': round(total_savings, 2),
        'savings_rate': round(savings_rate, 1),
        'avg_monthly_income': round(total_income / months, 2),
        'avg_monthly_expense': round(total_expense / months, 2),
        'avg_monthly_savings': round(total_savings / months, 2)
    }


def get_cash_details(user_id: int) -> List[Dict[str, Any]]:
    """Detalle de saldos por banco."""
    from app.models import Bank, BankBalance
    today = date.today()
    
    banks = Bank.query.filter_by(user_id=user_id).all()
    details = []
    
    for bank in banks:
        balance = BankBalance.query.filter_by(
            user_id=user_id, bank_id=bank.id, 
            year=today.year, month=today.month
        ).first()
        amount = balance.amount if balance else 0
        details.append({
            'name': bank.name,
            'icon': bank.icon,
            'amount': round(amount, 2)
        })
    
    return sorted(details, key=lambda x: x['amount'], reverse=True)


def get_top_movers_for_user(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Top movers del día: acciones, ETF, cripto y metales (Commodity) del portfolio con mayor |% cambio día|.
    Solo entran si hay day_change_percent (precio actual no basta: sin cierre previo no se sabe el movimiento del día).
    """
    holdings = (
        db.session.query(Asset)
        .join(PortfolioHolding, PortfolioHolding.asset_id == Asset.id)
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .filter(Asset.asset_type.in_(['Stock', 'ETF', 'Crypto', 'Commodity']))
        .filter(Asset.day_change_percent.isnot(None))
        .distinct()
        .all()
    )
    if not holdings:
        return []
    sorted_assets = sorted(
        holdings,
        key=lambda a: abs(a.day_change_percent or 0),
        reverse=True,
    )
    return [
        {
            'asset_id': a.id,
            'symbol': a.symbol or '',
            'name': a.name or a.symbol or '',
            'day_change_percent': round(a.day_change_percent, 2),
            'current_price': round(a.current_price, 2) if a.current_price else None,
        }
        for a in sorted_assets[:limit]
    ]


def get_portfolio_details(user_id: int, top_n: int = 5) -> Dict[str, Any]:
    """Detalle del portfolio: top holdings y P&L. Usa stocks_metrics (pnl_lib)."""
    metrics = compute_stocks_metrics(user_id, top_n=top_n)
    return {
        'total_value': metrics['total_value'],
        'total_cost': metrics['total_cost'],
        'total_pnl': metrics['total_pnl'],
        'total_pnl_pct': metrics['total_pnl_pct'],
        'holdings_count': metrics['holdings_count'],
        'top_holdings': metrics['top_holdings'],
    }


def get_crypto_details(user_id: int) -> Dict[str, Any]:
    """Detalle de crypto con posiciones. Claves unificadas: total_value, total_cost, total_pnl, total_pnl_pct."""
    metrics = compute_crypto_metrics(user_id)
    return {
        'total_value': metrics.get('total_value', 0),
        'total_cost': metrics.get('total_cost', 0),
        'total_pnl': metrics.get('total_pnl', 0),
        'total_pnl_pct': metrics.get('total_pnl_pct', 0),
        'posiciones': metrics.get('posiciones', [])[:5],
    }


def get_metales_details(user_id: int) -> Dict[str, Any]:
    """Detalle de metales preciosos. Claves unificadas: total_value, total_cost, total_pnl, total_pnl_pct."""
    metrics = compute_metales_metrics(user_id)
    return {
        'total_value': metrics.get('total_value', 0),
        'total_cost': metrics.get('total_cost', 0),
        'total_pnl': metrics.get('total_pnl', 0),
        'total_pnl_pct': metrics.get('total_pnl_pct', 0),
        'posiciones': metrics.get('posiciones', []),
    }


def get_real_estate_details(user_id: int) -> Dict[str, Any]:
    """Detalle de inmuebles."""
    try:
        from app.models import RealEstateProperty
        props = RealEstateProperty.query.filter_by(user_id=user_id).all()
        total = sum(p.get_estimated_value() for p in props)
        return {
            'total_value': round(total, 2),
            'properties': [
                {'id': p.id, 'address': p.address, 'type': p.property_type, 'value': p.get_estimated_value(), 'icon': p.get_icon()}
                for p in props
            ],
        }
    except OperationalError:
        return {'total_value': 0, 'properties': []}


def get_debt_details(user_id: int) -> Dict[str, Any]:
    """Detalle de deudas con próximas cuotas."""
    try:
        from app.models import DebtPlan, Expense, User
        plans = DebtPlan.query.filter_by(user_id=user_id, status='ACTIVE').all()
    except OperationalError:
        return {'total_debt': 0, 'total_monthly': 0, 'plans_count': 0, 'plans': []}

    total_debt = 0
    total_monthly = 0
    debt_list = []
    
    today = date.today()
    
    for plan in plans:
        # Calcular pagos realizados y restantes
        paid_count = plan.installment_expenses.filter(Expense.date <= today).count()
        remaining_payments = max(0, plan.months - paid_count)
        remaining = plan.monthly_payment * remaining_payments
        
        total_debt += remaining
        total_monthly += plan.monthly_payment
        
        # Próxima cuota
        next_payment = Expense.query.filter(
            Expense.debt_plan_id == plan.id,
            Expense.date > today
        ).order_by(Expense.date.asc()).first()

        # Última cuota (fin del plan) para ordenar por "próximo a expirar"
        last_payment = Expense.query.filter(
            Expense.debt_plan_id == plan.id
        ).order_by(Expense.date.desc()).first()
        
        debt_list.append({
            'name': plan.name,
            'remaining': round(remaining, 2),
            'installment': round(plan.monthly_payment, 2),
            'next_date': next_payment.date.strftime('%d/%m/%Y') if next_payment else None,
            'remaining_payments': remaining_payments,
            'end_date': last_payment.date.strftime('%d/%m/%Y') if last_payment else None,
            'end_date_dt': last_payment.date if last_payment else None,
        })

    # Límite de endeudamiento (misma lógica que /debts)
    limit_info = None
    try:
        from app.services.debt_service import DebtService
        user = User.query.get(user_id)
        if user:
            limit_info = DebtService.get_debt_limit_info(user)
    except Exception:
        limit_info = None

    # Mini calendario (6 barras): -2, -1, actual, +1, +2, +3
    mini_schedule = []
    try:
        from dateutil.relativedelta import relativedelta
        from collections import defaultdict

        start = date(today.year, today.month, 1) + relativedelta(months=-2)
        end = date(today.year, today.month, 1) + relativedelta(months=+3)

        expenses = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.debt_plan_id.isnot(None),
            Expense.date >= start,
            Expense.date < (end + relativedelta(months=1)),
        ).all()
        by_month = defaultdict(float)
        for e in expenses:
            k = e.date.strftime('%Y-%m')
            by_month[k] += float(e.amount or 0)

        _MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
        current = start
        while current <= end:
            key = current.strftime('%Y-%m')
            label = f"{_MESES[current.month - 1]} {current.year}"
            mini_schedule.append({
                'month_key': key,
                'month_label': label,
                'amount': round(by_month.get(key, 0.0), 2),
            })
            current = current + relativedelta(months=1)
    except Exception:
        mini_schedule = []

    # Planes próximos a expirar (por end_date ascendente, si existe)
    expiring = sorted(
        [d for d in debt_list if d.get('end_date_dt')],
        key=lambda x: x.get('end_date_dt'),
    )[:5]

    return {
        'total_debt': round(total_debt, 2),
        'total_monthly': round(total_monthly, 2),
        'plans_count': len(plans),
        'plans': sorted(debt_list, key=lambda x: x['remaining'], reverse=True),
        'expiring_plans': expiring,
        'limit_info': limit_info,
        'mini_schedule': mini_schedule,
    }


def get_income_expense_by_month(user_id: int, months: int = 12) -> List[Dict[str, Any]]:
    """Ingresos y gastos por mes para gráfico de barras."""
    from app.services.income_expense_aggregator import (
        get_income_monthly_totals_with_adjustment,
        get_expense_monthly_totals_with_adjustment,
    )
    
    income_totals = get_income_monthly_totals_with_adjustment(user_id, months=months)
    expense_totals = get_expense_monthly_totals_with_adjustment(user_id, months=months)
    
    result = []
    for inc, exp in zip(income_totals, expense_totals):
        result.append({
            'month_label': inc.get('month_label', ''),
            'income': round(inc.get('total', 0), 2),
            'expense': round(exp.get('total', 0), 2),
            'balance': round(inc.get('total', 0) - exp.get('total', 0), 2)
        })
    
    return result


def get_top_expenses_month(user_id: int) -> Dict[str, Any]:
    """Top 5 categorías de gastos del mes actual vs media."""
    from app.models import Expense, ExpenseCategory
    from sqlalchemy import func
    
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Gastos del mes actual por categoría
    current_expenses = db.session.query(
        ExpenseCategory.name,
        ExpenseCategory.icon,
        func.sum(Expense.amount).label('total')
    ).join(Expense.category).filter(
        Expense.user_id == user_id,
        Expense.date >= current_month_start,
        Expense.date <= today
    ).group_by(ExpenseCategory.id).order_by(func.sum(Expense.amount).desc()).limit(5).all()
    
    # Media de los últimos 6 meses por categoría
    six_months_ago = today - relativedelta(months=6)
    avg_expenses = db.session.query(
        ExpenseCategory.name,
        func.sum(Expense.amount).label('total')
    ).join(Expense.category).filter(
        Expense.user_id == user_id,
        Expense.date >= six_months_ago,
        Expense.date < current_month_start
    ).group_by(ExpenseCategory.id).all()
    
    avg_by_cat = {e.name: round(e.total / 6, 2) for e in avg_expenses}
    
    top_expenses = []
    for exp in current_expenses:
        avg = avg_by_cat.get(exp.name, 0)
        diff = exp.total - avg
        diff_pct = (diff / avg * 100) if avg > 0 else 0
        top_expenses.append({
            'category': exp.name,
            'icon': exp.icon or '📦',
            'amount': round(exp.total, 2),
            'avg': avg,
            'diff': round(diff, 2),
            'diff_pct': round(diff_pct, 1)
        })
    
    total_month = sum(e['amount'] for e in top_expenses)
    return {
        'month': today.strftime('%B %Y'),
        'total': round(total_month, 2),
        'categories': top_expenses
    }


def get_upcoming_payments(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Próximos pagos: cuotas de deuda y gastos recurrentes."""
    from app.models import Expense, DebtPlan
    
    today = date.today()
    end_date = today + relativedelta(days=days)
    
    # Próximas cuotas de deuda
    upcoming = []
    
    debt_payments = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.debt_plan_id.isnot(None),
        Expense.date > today,
        Expense.date <= end_date
    ).order_by(Expense.date.asc()).all()
    
    for payment in debt_payments:
        upcoming.append({
            'type': 'debt',
            'name': payment.debt_plan.name if payment.debt_plan else 'Cuota',
            'amount': round(payment.amount, 2),
            'date': payment.date.strftime('%d/%m'),
            'days_until': (payment.date - today).days,
            'icon': '💳'
        })
    
    return sorted(upcoming, key=lambda x: x['days_until'])[:10]


def get_portfolio_aggregate(user_id: int):
    """
    PortfolioSnapshot agregado: stocks + crypto + metales.
    Usa pnl_lib para totales unificados.
    """
    stocks = compute_stocks_metrics(user_id)
    crypto = compute_crypto_metrics(user_id)
    metales = compute_metales_metrics(user_id)
    categories = {
        'stocks': stocks['snapshot'],
        'crypto': crypto['snapshot'],
        'metales': metales['snapshot'],
    }
    return create_portfolio_snapshot(categories)


def get_investments_summary(user_id: int) -> Dict[str, Any]:
    """Rentabilidad consolidada de todas las inversiones. Usa PortfolioSnapshot."""
    agg = get_portfolio_aggregate(user_id)
    c = agg.categories
    return {
        'total_value': round(agg.total_value, 2),
        'total_cost': round(agg.total_cost, 2),
        'total_pnl': round(agg.total_pnl, 2),
        'total_pnl_pct': round(agg.total_pnl_pct, 1),
        'by_type': [
            {'name': 'Portfolio', 'value': c['stocks'].total_value, 'pnl': c['stocks'].total_pnl, 'pnl_pct': c['stocks'].total_pnl_pct},
            {'name': 'Crypto', 'value': c['crypto'].total_value, 'pnl': c['crypto'].total_pnl, 'pnl_pct': c['crypto'].total_pnl_pct},
            {'name': 'Metales', 'value': c['metales'].total_value, 'pnl': c['metales'].total_pnl, 'pnl_pct': c['metales'].total_pnl_pct},
        ],
    }


def get_recent_transactions(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Últimas transacciones (ingresos y gastos)."""
    from app.models import Income, Expense
    
    incomes = Income.query.filter_by(user_id=user_id).order_by(Income.date.desc()).limit(limit).all()
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).limit(limit).all()
    
    transactions = []
    for inc in incomes:
        transactions.append({
            'type': 'income',
            'description': inc.description or (inc.category.name if inc.category else 'Ingreso'),
            'amount': round(inc.amount, 2),
            'date': inc.date,
            'date_str': inc.date.strftime('%d/%m'),
            'icon': inc.category.icon if inc.category else '💵'
        })
    
    for exp in expenses:
        transactions.append({
            'type': 'expense',
            'description': exp.description or (exp.category.name if exp.category else 'Gasto'),
            'amount': round(exp.amount, 2),
            'date': exp.date,
            'date_str': exp.date.strftime('%d/%m'),
            'icon': exp.category.icon if exp.category else '🛒'
        })
    
    return sorted(transactions, key=lambda x: x['date'], reverse=True)[:limit]


def get_currency_exposure(user_id: int) -> Dict[str, Any]:
    """Exposición por divisa de los activos."""
    holdings = (
        PortfolioHolding.query
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(PortfolioHolding.asset)
        .all()
    )
    
    by_currency = {}
    for h in holdings:
        price = h.current_price or (h.asset.current_price if h.asset else 0) or 0
        value = h.quantity * price
        currency = h.asset.currency if h.asset else 'EUR'
        
        if currency not in by_currency:
            by_currency[currency] = 0
        by_currency[currency] += value
    
    # Añadir cash (asumimos EUR)
    cash = get_cash_total(user_id)
    by_currency['EUR'] = by_currency.get('EUR', 0) + cash
    
    total = sum(by_currency.values())
    exposure = []
    for currency, value in sorted(by_currency.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total * 100) if total > 0 else 0
        value_eur = convert_to_eur(value, currency) if currency != 'EUR' else value
        exposure.append({
            'currency': currency,
            'value': round(value, 2),
            'value_eur': round(value_eur, 2),
            'pct': round(pct, 1)
        })
    
    return {
        'total_eur': round(sum(e['value_eur'] for e in exposure), 2),
        'currencies': exposure[:6]
    }


def get_year_comparison(user_id: int) -> Dict[str, Any]:
    """Comparativa año actual vs anterior."""
    from app.services.income_expense_aggregator import (
        get_income_monthly_totals_with_adjustment,
        get_expense_monthly_totals_with_adjustment,
    )
    
    today = date.today()
    current_month = today.month
    
    # Año actual (hasta el mes actual)
    current_income = get_income_monthly_totals_with_adjustment(user_id, months=current_month)
    current_expense = get_expense_monthly_totals_with_adjustment(user_id, months=current_month)
    
    current_total_income = sum(i.get('total', 0) for i in current_income)
    current_total_expense = sum(e.get('total', 0) for e in current_expense)
    current_savings = current_total_income - current_total_expense
    
    # Año anterior (mismos meses)
    prev_income = get_income_monthly_totals_with_adjustment(user_id, months=current_month + 12)[:current_month]
    prev_expense = get_expense_monthly_totals_with_adjustment(user_id, months=current_month + 12)[:current_month]
    
    prev_total_income = sum(i.get('total', 0) for i in prev_income)
    prev_total_expense = sum(e.get('total', 0) for e in prev_expense)
    prev_savings = prev_total_income - prev_total_expense
    
    def calc_change(current, prev):
        if prev == 0:
            return 0
        return round((current - prev) / prev * 100, 1)
    
    return {
        'current_year': today.year,
        'prev_year': today.year - 1,
        'months_compared': current_month,
        'income': {
            'current': round(current_total_income, 2),
            'prev': round(prev_total_income, 2),
            'change_pct': calc_change(current_total_income, prev_total_income)
        },
        'expense': {
            'current': round(current_total_expense, 2),
            'prev': round(prev_total_expense, 2),
            'change_pct': calc_change(current_total_expense, prev_total_expense)
        },
        'savings': {
            'current': round(current_savings, 2),
            'prev': round(prev_savings, 2),
            'change_pct': calc_change(current_savings, prev_savings)
        }
    }


def get_financial_health_score(user_id: int) -> Dict[str, Any]:
    """Índice de salud financiera completo con análisis detallado."""
    from app.services.income_expense_aggregator import (
        get_income_monthly_totals_with_adjustment,
        get_expense_monthly_totals_with_adjustment,
    )
    
    savings = get_savings_rate(user_id, months=12)
    breakdown = get_net_worth_breakdown(user_id)
    history = get_net_worth_history(user_id, months=12)
    
    # Datos mensuales para análisis
    income_monthly = get_income_monthly_totals_with_adjustment(user_id, months=12)
    expense_monthly = get_expense_monthly_totals_with_adjustment(user_id, months=12)
    
    monthly_savings_list = [
        inc.get('total', 0) - exp.get('total', 0) 
        for inc, exp in zip(income_monthly, expense_monthly)
    ]
    
    # ============ COMPONENTES DEL SCORE ============
    scores = {}
    details = {}
    
    # 1. TASA DE AHORRO (0-20 puntos) - ideal >= 20%
    savings_rate = savings['savings_rate']
    if savings_rate >= 30:
        scores['savings_rate'] = 20
    elif savings_rate >= 20:
        scores['savings_rate'] = 17
    elif savings_rate >= 10:
        scores['savings_rate'] = 12
    elif savings_rate >= 0:
        scores['savings_rate'] = 5
    else:
        scores['savings_rate'] = 0
    
    details['savings_rate'] = {
        'score': scores['savings_rate'],
        'max': 20,
        'label': 'Tasa de Ahorro',
        'value': f'{savings_rate:.1f}%',
        'ideal': '≥ 20%',
        'status': 'good' if savings_rate >= 20 else 'warning' if savings_rate >= 10 else 'bad',
        'description': 'Porcentaje de ingresos que ahorras'
    }
    
    # 2. CONSISTENCIA DEL AHORRO (0-15 puntos) - baja variabilidad mensual
    if len(monthly_savings_list) > 1 and np.mean(monthly_savings_list) != 0:
        savings_std = np.std(monthly_savings_list)
        savings_mean = abs(np.mean(monthly_savings_list))
        consistency = 1 - min(1, savings_std / savings_mean) if savings_mean > 0 else 0
        consistency_pct = consistency * 100
    else:
        consistency_pct = 50
    
    if consistency_pct >= 80:
        scores['consistency'] = 15
    elif consistency_pct >= 60:
        scores['consistency'] = 12
    elif consistency_pct >= 40:
        scores['consistency'] = 8
    else:
        scores['consistency'] = 4
    
    # Meses con ahorro positivo
    positive_months = sum(1 for s in monthly_savings_list if s > 0)
    
    details['consistency'] = {
        'score': scores['consistency'],
        'max': 15,
        'label': 'Consistencia',
        'value': f'{positive_months}/12 meses',
        'ideal': '12/12 meses',
        'status': 'good' if positive_months >= 10 else 'warning' if positive_months >= 6 else 'bad',
        'description': 'Meses con ahorro positivo'
    }
    
    # 3. DIVERSIFICACIÓN (0-15 puntos)
    asset_values = {
        'cash': breakdown['cash'],
        'portfolio': breakdown['portfolio'],
        'crypto': breakdown['crypto'],
        'metales': breakdown['metales'],
        'real_estate': breakdown.get('real_estate', 0),
    }
    assets_with_value = sum(1 for v in asset_values.values() if v > 0)
    
    # Calcular concentración (Herfindahl)
    total_assets = breakdown['assets_total']
    if total_assets > 0:
        concentration = sum((v/total_assets)**2 for v in asset_values.values() if v > 0)
        diversification_score = (1 - concentration) * 100
    else:
        diversification_score = 0
    
    if diversification_score >= 60 and assets_with_value >= 3:
        scores['diversification'] = 15
    elif diversification_score >= 40 and assets_with_value >= 2:
        scores['diversification'] = 12
    elif assets_with_value >= 2:
        scores['diversification'] = 8
    else:
        scores['diversification'] = 4
    
    details['diversification'] = {
        'score': scores['diversification'],
        'max': 15,
        'label': 'Diversificación',
        'value': f'{assets_with_value} tipos',
        'ideal': '3-4 tipos',
        'status': 'good' if assets_with_value >= 3 else 'warning' if assets_with_value >= 2 else 'bad',
        'description': 'Variedad de activos',
        'breakdown': {k: round(v/total_assets*100, 1) if total_assets > 0 else 0 for k, v in asset_values.items()}
    }
    
    # 4. RATIO DEUDA/PATRIMONIO (0-15 puntos)
    debt_ratio = (breakdown['debt'] / breakdown['assets_total'] * 100) if breakdown['assets_total'] > 0 else 0
    
    if debt_ratio == 0:
        scores['debt_ratio'] = 15
    elif debt_ratio < 10:
        scores['debt_ratio'] = 13
    elif debt_ratio < 20:
        scores['debt_ratio'] = 10
    elif debt_ratio < 40:
        scores['debt_ratio'] = 6
    else:
        scores['debt_ratio'] = 2
    
    details['debt_ratio'] = {
        'score': scores['debt_ratio'],
        'max': 15,
        'label': 'Ratio Deuda',
        'value': f'{debt_ratio:.1f}%',
        'ideal': '< 20%',
        'status': 'good' if debt_ratio < 20 else 'warning' if debt_ratio < 40 else 'bad',
        'description': 'Deuda vs activos totales',
        'debt_amount': breakdown['debt']
    }
    
    # 5. FONDO DE EMERGENCIA (0-15 puntos)
    avg_monthly_expense = savings['avg_monthly_expense']
    months_runway = (breakdown['cash'] / avg_monthly_expense) if avg_monthly_expense > 0 else 0
    
    if months_runway >= 6:
        scores['emergency_fund'] = 15
    elif months_runway >= 3:
        scores['emergency_fund'] = 12
    elif months_runway >= 2:
        scores['emergency_fund'] = 8
    elif months_runway >= 1:
        scores['emergency_fund'] = 5
    else:
        scores['emergency_fund'] = 2
    
    details['emergency_fund'] = {
        'score': scores['emergency_fund'],
        'max': 15,
        'label': 'Fondo Emergencia',
        'value': f'{months_runway:.1f} meses',
        'ideal': '6+ meses',
        'status': 'good' if months_runway >= 6 else 'warning' if months_runway >= 3 else 'bad',
        'description': 'Meses de gastos cubiertos',
        'target_amount': round(avg_monthly_expense * 6, 2),
        'current_amount': breakdown['cash']
    }
    
    # 6. CRECIMIENTO PATRIMONIAL (0-10 puntos)
    if len(history) >= 2:
        first_nw = history[0]['net_worth']
        last_nw = history[-1]['net_worth']
        if first_nw > 0:
            growth_pct = ((last_nw - first_nw) / first_nw) * 100
        else:
            growth_pct = 100 if last_nw > 0 else 0
    else:
        growth_pct = 0
    
    if growth_pct >= 20:
        scores['growth'] = 10
    elif growth_pct >= 10:
        scores['growth'] = 8
    elif growth_pct >= 5:
        scores['growth'] = 6
    elif growth_pct >= 0:
        scores['growth'] = 4
    else:
        scores['growth'] = 0
    
    details['growth'] = {
        'score': scores['growth'],
        'max': 10,
        'label': 'Crecimiento',
        'value': f'{growth_pct:.1f}%',
        'ideal': '> 10% anual',
        'status': 'good' if growth_pct >= 10 else 'warning' if growth_pct >= 0 else 'bad',
        'description': 'Crecimiento últimos 12 meses'
    }
    
    # 7. INVERSIÓN VS AHORRO (0-10 puntos) - ideal tener dinero invertido
    investments_total = breakdown['portfolio'] + breakdown['crypto'] + breakdown['metales']
    investment_ratio = (investments_total / breakdown['assets_total'] * 100) if breakdown['assets_total'] > 0 else 0
    
    if investment_ratio >= 50:
        scores['investment_ratio'] = 10
    elif investment_ratio >= 30:
        scores['investment_ratio'] = 8
    elif investment_ratio >= 15:
        scores['investment_ratio'] = 5
    else:
        scores['investment_ratio'] = 2
    
    details['investment_ratio'] = {
        'score': scores['investment_ratio'],
        'max': 10,
        'label': 'Ratio Inversión',
        'value': f'{investment_ratio:.1f}%',
        'ideal': '30-70%',
        'status': 'good' if 30 <= investment_ratio <= 70 else 'warning' if investment_ratio > 0 else 'bad',
        'description': '% invertido vs cash'
    }
    
    # ============ CALCULAR SCORE TOTAL ============
    total_score = sum(scores.values())
    max_score = sum(d['max'] for d in details.values())
    
    # Normalizar a 100
    normalized_score = round((total_score / max_score) * 100) if max_score > 0 else 0
    
    # Determinar nivel
    if normalized_score >= 80:
        level = 'Excelente'
        color = 'green'
        emoji = '🌟'
    elif normalized_score >= 65:
        level = 'Muy Bueno'
        color = 'blue'
        emoji = '✅'
    elif normalized_score >= 50:
        level = 'Bueno'
        color = 'blue'
        emoji = '👍'
    elif normalized_score >= 35:
        level = 'Regular'
        color = 'yellow'
        emoji = '⚠️'
    else:
        level = 'Mejorable'
        color = 'red'
        emoji = '🔴'
    
    # ============ GENERAR CONSEJOS ============
    tips = _generate_health_tips(details, savings_rate, debt_ratio, months_runway, 
                                  investment_ratio, growth_pct, positive_months)
    
    # ============ ALERTAS ============
    alerts = _generate_health_alerts(user_id, monthly_savings_list, debt_ratio, months_runway)
    
    # ============ HISTÓRICO DEL SCORE ============
    score_history = _calculate_score_history(user_id)
    
    return {
        'score': normalized_score,
        'raw_score': total_score,
        'max_score': max_score,
        'level': level,
        'color': color,
        'emoji': emoji,
        'components': details,
        'tips': tips,
        'alerts': alerts,
        'score_history': score_history,
        'summary': {
            'savings_rate': savings_rate,
            'debt_ratio': debt_ratio,
            'months_runway': months_runway,
            'investment_ratio': investment_ratio,
            'growth_pct': growth_pct,
            'assets_count': assets_with_value,
            'positive_months': positive_months
        }
    }


def _generate_health_tips(details, savings_rate, debt_ratio, months_runway, 
                          investment_ratio, growth_pct, positive_months):
    """Genera consejos priorizados basados en las métricas."""
    tips = []
    
    # Priorizar por impacto
    if months_runway < 3:
        tips.append({
            'priority': 'high',
            'icon': '🚨',
            'title': 'Fondo de emergencia bajo',
            'text': f'Tienes solo {months_runway:.1f} meses de gastos cubiertos. Objetivo: 6 meses.',
            'action': f'Ahorra {details["emergency_fund"]["target_amount"] - details["emergency_fund"]["current_amount"]:.0f}€ más'
        })
    
    if debt_ratio > 30:
        tips.append({
            'priority': 'high',
            'icon': '💳',
            'title': 'Deuda elevada',
            'text': f'Tu deuda representa el {debt_ratio:.1f}% de tus activos.',
            'action': 'Prioriza reducir deuda antes de invertir más'
        })
    
    if savings_rate < 10:
        tips.append({
            'priority': 'high',
            'icon': '💰',
            'title': 'Tasa de ahorro baja',
            'text': f'Solo ahorras el {savings_rate:.1f}% de tus ingresos.',
            'action': 'Revisa gastos no esenciales y automatiza el ahorro'
        })
    
    if investment_ratio < 20 and months_runway >= 3:
        tips.append({
            'priority': 'medium',
            'icon': '📈',
            'title': 'Poco invertido',
            'text': f'Solo el {investment_ratio:.1f}% está invertido.',
            'action': 'Considera invertir parte del exceso de liquidez'
        })
    
    if positive_months < 8:
        tips.append({
            'priority': 'medium',
            'icon': '📉',
            'title': 'Ahorro inconsistente',
            'text': f'Solo {positive_months} de 12 meses con ahorro positivo.',
            'action': 'Establece un presupuesto mensual fijo'
        })
    
    if details['diversification']['score'] < 10:
        tips.append({
            'priority': 'low',
            'icon': '🎯',
            'title': 'Poca diversificación',
            'text': 'Tus activos están muy concentrados.',
            'action': 'Diversifica entre diferentes tipos de activos'
        })
    
    if growth_pct < 5 and savings_rate > 0:
        tips.append({
            'priority': 'low',
            'icon': '🐢',
            'title': 'Crecimiento lento',
            'text': f'Tu patrimonio creció solo {growth_pct:.1f}% este año.',
            'action': 'Revisa la rentabilidad de tus inversiones'
        })
    
    return tips[:5]


def _generate_health_alerts(user_id, monthly_savings_list, debt_ratio, months_runway):
    """Genera alertas importantes."""
    alerts = []
    
    # Alerta si los últimos 2 meses fueron negativos
    if len(monthly_savings_list) >= 2:
        if monthly_savings_list[-1] < 0 and monthly_savings_list[-2] < 0:
            alerts.append({
                'type': 'warning',
                'icon': '⚠️',
                'text': 'Llevas 2 meses consecutivos gastando más de lo que ingresas'
            })
    
    # Alerta de fondo de emergencia crítico
    if months_runway < 1:
        alerts.append({
            'type': 'danger',
            'icon': '🚨',
            'text': 'Tu fondo de emergencia cubre menos de 1 mes de gastos'
        })
    
    # Alerta de deuda crítica
    if debt_ratio > 50:
        alerts.append({
            'type': 'danger',
            'icon': '💳',
            'text': 'Tu nivel de deuda es crítico (>50% de tus activos)'
        })
    
    return alerts


def _calculate_score_history(user_id):
    """Calcula histórico simplificado del score (últimos 6 meses)."""
    # Por ahora retornamos datos simplificados
    # En una versión futura se podría calcular el score real histórico
    today = date.today()
    history = []
    
    for i in range(5, -1, -1):
        d = today - relativedelta(months=i)
        history.append({
            'month': d.strftime('%b'),
            'year': d.year
        })
    
    return history


def _build_dashboard_history(user_id: int) -> Dict[str, Any]:
    """
    Construye la parte de histórico del dashboard (serie completa + metadatos).
    No incluye aún el desglose actual ni widgets.
    """
    history_data = get_full_net_worth_history(user_id)
    history = history_data["history"]

    return {
        "history": history,
        "history_meta": {
            "total_months": history_data["total_months"],
            "start_date": history_data.get("start_date"),
            "start_label": history_data.get("start_label"),
            "years_available": history_data.get("years_available", 1),
        },
    }


def _build_dashboard_current_from_history(breakdown: Dict[str, Any], history: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Construye las métricas que dependen del último punto del histórico
    y del patrimonio actual (cambios mensuales, YTD, etc.).
    """
    # Calcular cambio vs mes anterior
    if len(history) >= 2:
        current = history[-1]["net_worth"]
        previous = history[-2]["net_worth"]
        month_change = current - previous
        month_change_pct = (month_change / previous * 100) if previous > 0 else 0
    else:
        month_change = 0
        month_change_pct = 0

    # Calcular cambio vs inicio del año
    current_year = date.today().year
    year_start = next(
        (h for h in history if h["year"] == current_year and h["month"] == 1),
        None,
    )
    if year_start:
        ytd_change = breakdown["net_worth"] - year_start["net_worth"]
        ytd_change_pct = (
            (ytd_change / year_start["net_worth"] * 100)
            if year_start["net_worth"] > 0
            else 0
        )
    else:
        ytd_change = 0
        ytd_change_pct = 0

    return {
        "net_worth": breakdown["net_worth"],
        "changes": {
            "month": round(month_change, 2),
            "month_pct": round(month_change_pct, 1),
            "ytd": round(ytd_change, 2),
            "ytd_pct": round(ytd_change_pct, 1),
        },
        # Punto actual explícito (último punto del histórico)
        "current_point": history[-1] if history else None,
    }


def get_dashboard_summary(user_id: int) -> Dict[str, Any]:
    """
    Resumen completo para el dashboard principal.
    Combina patrimonio, desglose, proyecciones y métricas de ahorro.
    """
    breakdown = get_net_worth_breakdown(user_id)
    history_block = _build_dashboard_history(user_id)
    history = history_block["history"]
    projections = get_net_worth_projection(user_id)
    savings = get_savings_rate(user_id, months=12)

    # Detalles por categoría
    cash_details = get_cash_details(user_id)
    portfolio_details = get_portfolio_details(user_id)
    crypto_details = get_crypto_details(user_id)
    metales_details = get_metales_details(user_id)
    real_estate_details = get_real_estate_details(user_id)
    debt_details = get_debt_details(user_id)

    # Datos para gráficos adicionales
    income_expense_monthly = get_income_expense_by_month(user_id, months=12)

    # Nuevos widgets
    top_expenses = get_top_expenses_month(user_id)
    upcoming_payments = get_upcoming_payments(user_id)
    investments_summary = get_investments_summary(user_id)
    recent_transactions = get_recent_transactions(user_id)
    currency_exposure = get_currency_exposure(user_id)
    from app.services.income_expense_aggregator import (
        get_expense_category_summary_with_adjustment,
        get_income_category_summary_with_adjustment,
    )

    expense_category_summary = get_expense_category_summary_with_adjustment(
        user_id, months=12
    )
    income_category_summary = get_income_category_summary_with_adjustment(
        user_id, months=12
    )
    year_comparison = get_year_comparison(user_id)
    health_score = get_financial_health_score(user_id)
    try:
        from app.services.recommendation_service import RecommendationService
        recommendations = RecommendationService.build_for_dashboard(user_id, health_score=health_score)
    except Exception:
        recommendations = []

    current_block = _build_dashboard_current_from_history(breakdown, history)
    # DAY % y EUR (broker real + crypto + metales). Pueden ser None.
    try:
        day_inv = get_investments_day_change(user_id)
        if day_inv:
            current_block["changes"]["day_pct"], current_block["changes"]["day_eur"] = day_inv
        else:
            current_block["changes"]["day_pct"] = None
            current_block["changes"]["day_eur"] = None
    except Exception:
        current_block["changes"]["day_pct"] = None
        current_block["changes"]["day_eur"] = None
    top_movers = get_top_movers_for_user(user_id, limit=5)
    from app.services.portfolio_benchmarks_cache import get_market_indices_snapshot

    market_indices = get_market_indices_snapshot(user_id)
    commodities = get_commodities_snapshot(user_id)

    # Mantener la estructura existente para compatibilidad con templates
    return {
        "net_worth": current_block["net_worth"],
        "breakdown": breakdown,
        "history": history_block["history"],
        "history_meta": history_block["history_meta"],
        "projections": projections,
        "savings": savings,
        "changes": current_block["changes"],
        # Detalles por categoría
        "cash_details": cash_details,
        "portfolio_details": portfolio_details,
        "crypto_details": crypto_details,
        "metales_details": metales_details,
        "real_estate_details": real_estate_details,
        "debt_details": debt_details,
        "income_expense_monthly": income_expense_monthly,
        # Nuevos widgets
        "top_expenses": top_expenses,
        "upcoming_payments": upcoming_payments,
        "investments_summary": investments_summary,
        "recent_transactions": recent_transactions,
        "currency_exposure": currency_exposure,
        "year_comparison": year_comparison,
        "health_score": health_score,
        "recommendations": recommendations,
        "expense_category_summary": expense_category_summary,
        "income_category_summary": income_category_summary,
        # Campos nuevos para futuras optimizaciones de cache
        "history_block": history_block,
        "current_block": current_block,
        "top_movers": top_movers,
        "market_indices": market_indices,
        "commodities": commodities,
    }
