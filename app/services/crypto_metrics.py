"""
Métricas para el módulo Cryptomonedas
Fiat, cuasi-fiat, rentabilidad, rewards
Usa pnl_lib para fórmulas unificadas de P&L.
"""
from typing import Dict, List, Any

from app.services.metrics.pnl_lib import (
    create_position_snapshot,
    create_asset_category_snapshot,
)

# Stablecoins = cuasi-fiat
STABLECOINS = {'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP'}


def get_crypto_holdings(user_id: int):
    """Obtiene holdings de crypto del usuario (cuentas Revolut o assets tipo Crypto)"""
    from app.models import PortfolioHolding, Asset

    holdings = (
        PortfolioHolding.query
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(PortfolioHolding.asset)
        .filter(Asset.asset_type == 'Crypto')
        .all()
    )
    return holdings


def _position_to_dict(ps) -> Dict[str, Any]:
    """Convierte PositionSnapshot a dict para templates (retrocompatibilidad)."""
    d = {
        'symbol': ps.symbol,
        'name': ps.name,
        'quantity': ps.quantity,
        'average_buy_price': ps.average_buy_price,
        'cost': ps.total_cost,
        'value': ps.total_value,
        'price': ps.current_price,
        'pl': ps.pnl,
        'pl_pct': ps.pnl_pct,
        'reward_quantity': ps.extra.get('reward_quantity', 0),
        'reward_value': ps.extra.get('reward_value', 0),
    }
    return d


def compute_crypto_metrics(user_id: int) -> Dict[str, Any]:
    """
    Calcula métricas del módulo Cryptomonedas usando pnl_lib.
    Devuelve dict con claves unificadas (total_cost, total_value, total_pnl, total_pnl_pct)
    y claves legacy (capital_invertido, valor_total, pl_total, pl_pct_total) para compatibilidad.
    """
    from app.models import Transaction, BrokerAccount, Broker

    holdings = get_crypto_holdings(user_id)
    if not holdings:
        return _empty_metrics()

    # Cuentas Revolut para rewards
    revolut_account_ids = [
        a.id for a in BrokerAccount.query
        .filter_by(user_id=user_id, is_active=True)
        .join(Broker)
        .filter(Broker.name == 'Revolut')
        .all()
    ]
    if not revolut_account_ids:
        revolut_account_ids = list({h.account_id for h in holdings})

    # Rewards: transacciones BUY con price=0 (staking rewards)
    rewards_quantity: Dict[str, float] = {}
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

    # Construir posiciones con pnl_lib
    cuasi_fiat = 0.0
    positions = []

    for h in holdings:
        asset = h.asset
        if not asset:
            continue
        symbol = asset.symbol or ''
        qty = h.quantity or 0
        total_cost = h.total_cost or 0
        price = asset.current_price or h.current_price or 0

        avg_price = (total_cost / qty) if qty > 0 else 0
        if h.average_buy_price is not None and h.average_buy_price > 0:
            avg_price = float(h.average_buy_price)

        reward_qty = rewards_quantity.get(symbol, 0)
        reward_value = reward_qty * price if price else 0

        is_stable = symbol.upper() in STABLECOINS
        if is_stable:
            total_value = qty * price if price else total_cost
            cuasi_fiat += total_value if price else qty

        pos = create_position_snapshot(
            symbol=symbol,
            name=asset.name or symbol,
            quantity=qty,
            average_buy_price=avg_price,
            total_cost=total_cost,
            current_price=price,
            extra={'reward_quantity': reward_qty, 'reward_value': reward_value},
        )
        positions.append(pos)
        if is_stable:
            cuasi_fiat += pos.total_value if price else qty

    snapshot = create_asset_category_snapshot(
        category='crypto',
        positions=positions,
        extra={'cuasi_fiat': cuasi_fiat, 'rewards_total': sum(p.extra.get('reward_value', 0) for p in positions)},
    )

    posiciones = [_position_to_dict(p) for p in snapshot.positions]

    # Claves unificadas + legacy para retrocompatibilidad
    return {
        'total_cost': snapshot.total_cost,
        'total_value': snapshot.total_value,
        'total_pnl': snapshot.total_pnl,
        'total_pnl_pct': snapshot.total_pnl_pct,
        'capital_invertido': snapshot.total_cost,
        'cuasi_fiat': snapshot.extra['cuasi_fiat'],
        'fiat_total': snapshot.total_cost + snapshot.extra['cuasi_fiat'],
        'valor_total': snapshot.total_value,
        'pl_total': snapshot.total_pnl,
        'pl_pct_total': snapshot.total_pnl_pct,
        'rewards_total': snapshot.extra['rewards_total'],
        'posiciones': posiciones,
        'holdings': holdings,
        'snapshot': snapshot,
    }


def _empty_metrics() -> Dict[str, Any]:
    snapshot = create_asset_category_snapshot(
        category='crypto', positions=[], extra={'cuasi_fiat': 0.0, 'rewards_total': 0.0}
    )
    return {
        'total_cost': 0.0,
        'total_value': 0.0,
        'total_pnl': 0.0,
        'total_pnl_pct': 0.0,
        'capital_invertido': 0.0,
        'cuasi_fiat': 0.0,
        'fiat_total': 0.0,
        'valor_total': 0.0,
        'pl_total': 0.0,
        'pl_pct_total': 0.0,
        'rewards_total': 0.0,
        'posiciones': [],
        'holdings': [],
        'snapshot': snapshot,
    }
