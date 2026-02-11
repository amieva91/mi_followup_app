"""
Métricas para el módulo Cryptomonedas
Fiat, cuasi-fiat, rentabilidad, rewards
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal

# Stablecoins = cuasi-fiat
STABLECOINS = {'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP'}


def get_crypto_holdings(user_id: int):
    """Obtiene holdings de crypto del usuario (cuentas Revolut o assets tipo Crypto)"""
    from app.models import PortfolioHolding, BrokerAccount, Asset

    # Cuentas Revolut o holdings con asset_type Crypto
    holdings = (
        PortfolioHolding.query
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(PortfolioHolding.asset)
        .filter(Asset.asset_type == 'Crypto')
        .all()
    )
    return holdings


def compute_crypto_metrics(user_id: int) -> Dict[str, Any]:
    """
    Calcula métricas del módulo Cryptomonedas:
    - capital_invertido: suma de costes de compras (aproximación fiat)
    - cuasi_fiat: valor en EUR de stablecoins (USDT, etc.)
    - fiat_total: capital_invertido + cuasi_fiat (con desglose)
    - posiciones: por activo con coste y valor actual
    - rentabilidad_total: P&L total incluyendo rewards
    - rewards_total: valor aproximado de rewards (cantidad * precio actual)
    """
    from app.models import Transaction, BrokerAccount, Asset, Broker

    holdings = get_crypto_holdings(user_id)
    if not holdings:
        return _empty_metrics()

    # Cuentas Revolut
    revolut_account_ids = [
        a.id for a in BrokerAccount.query
        .filter_by(user_id=user_id, is_active=True)
        .join(Broker)
        .filter(Broker.name == 'Revolut')
        .all()
    ]
    # Fallback: si no hay broker Revolut, usar cuentas de los holdings
    if not revolut_account_ids:
        revolut_account_ids = list({h.account_id for h in holdings})

    # Rewards: transacciones BUY con price=0 (staking rewards)
    rewards_quantity = {}
    for txn in Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.account_id.in_(revolut_account_ids),
        Transaction.asset_id.isnot(None),
        Transaction.transaction_type == 'BUY',
        Transaction.price == 0
    ).all():
        if txn.quantity and txn.asset and (txn.price is None or txn.price <= 0.01):
            sym = txn.asset.symbol or ''
            if sym:
                rewards_quantity[sym] = rewards_quantity.get(sym, 0) + txn.quantity

    capital_invertido = sum(h.total_cost or 0 for h in holdings)

    # Cuasi-fiat: valor de stablecoins
    cuasi_fiat = 0.0
    posiciones = []
    valor_total = 0.0

    for h in holdings:
        asset = h.asset
        if not asset:
            continue
        symbol = asset.symbol or ''
        qty = h.quantity or 0
        cost = h.total_cost or 0
        price = asset.current_price or h.current_price or 0
        value = qty * price if price else cost  # fallback a coste si no hay precio
        valor_total += value

        is_stable = symbol.upper() in STABLECOINS
        if is_stable:
            # 1:1 USD aprox; si tenemos precio usarlo, sino asumir 1
            cuasi_fiat += value if price else qty

        pl = value - cost if value else 0
        pl_pct = (pl / cost * 100) if cost > 0 else 0
        reward_qty = rewards_quantity.get(symbol, 0)
        reward_value = reward_qty * price if price else 0

        avg_price = (cost / qty) if qty > 0 else 0
        if h.average_buy_price is not None and h.average_buy_price > 0:
            avg_price = float(h.average_buy_price)
        posiciones.append({
            'symbol': symbol,
            'name': asset.name,
            'quantity': qty,
            'average_buy_price': avg_price,
            'cost': cost,
            'value': value,
            'price': price,
            'pl': pl,
            'pl_pct': pl_pct,
            'reward_quantity': reward_qty,
            'reward_value': reward_value,
        })

    rewards_total = sum(p['reward_value'] for p in posiciones)
    pl_total = valor_total - capital_invertido
    pl_pct_total = (pl_total / capital_invertido * 100) if capital_invertido > 0 else 0

    return {
        'capital_invertido': capital_invertido,
        'cuasi_fiat': cuasi_fiat,
        'fiat_total': capital_invertido + cuasi_fiat,
        'valor_total': valor_total,
        'total_cost': capital_invertido,
        'pl_total': pl_total,
        'pl_pct_total': pl_pct_total,
        'rewards_total': rewards_total,
        'posiciones': posiciones,
        'holdings': holdings,
    }


def _empty_metrics() -> Dict[str, Any]:
    return {
        'capital_invertido': 0.0,
        'cuasi_fiat': 0.0,
        'fiat_total': 0.0,
        'valor_total': 0.0,
        'total_cost': 0.0,
        'pl_total': 0.0,
        'pl_pct_total': 0.0,
        'rewards_total': 0.0,
        'posiciones': [],
        'holdings': [],
    }
