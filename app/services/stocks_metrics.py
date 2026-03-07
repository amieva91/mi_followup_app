"""
Métricas para el módulo Portfolio (Stock, ETF).
Usa pnl_lib para fórmulas unificadas de P&L.
"""
from typing import Dict, List, Any

from app.services.metrics.pnl_lib import (
    create_position_snapshot,
    create_asset_category_snapshot,
)


def get_stocks_holdings(user_id: int):
    """Holdings de acciones y ETF (asset_type Stock, ETF)."""
    from app.models import PortfolioHolding, Asset

    return (
        PortfolioHolding.query
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(PortfolioHolding.asset)
        .filter(Asset.asset_type.in_(['Stock', 'ETF']))
        .all()
    )


def _position_to_dict(ps) -> Dict[str, Any]:
    """Convierte PositionSnapshot a dict para templates (ticker, value, cost, pnl)."""
    return {
        'ticker': ps.symbol,
        'name': ps.name,
        'quantity': ps.quantity,
        'value': round(ps.total_value, 2),
        'cost': round(ps.total_cost, 2),
        'pnl': round(ps.pnl, 2),
        'pnl_pct': round(ps.pnl_pct, 1),
    }


def compute_stocks_metrics(user_id: int, top_n: int = None) -> Dict[str, Any]:
    """
    Métricas del módulo Portfolio (Stock+ETF) usando pnl_lib.
    Devuelve total_cost, total_value, total_pnl, total_pnl_pct y posiciones.
    """
    from app.services.currency_service import convert_to_eur

    holdings = get_stocks_holdings(user_id)
    if not holdings:
        return _empty_metrics(top_n)

    positions = []
    posiciones = []

    for h in holdings:
        asset = h.asset
        if not asset:
            continue
        qty = h.quantity or 0
        cost = h.total_cost or 0
        price = h.current_price or (asset.current_price if asset else 0) or 0
        currency = asset.currency or 'EUR'

        cost_eur = convert_to_eur(cost, currency)
        price_eur = convert_to_eur(price, currency) if price else 0

        avg_price = (cost_eur / qty) if qty else 0
        if h.average_buy_price is not None and h.average_buy_price > 0:
            avg_price = float(convert_to_eur(h.average_buy_price, currency))

        pos = create_position_snapshot(
            symbol=asset.symbol or 'N/A',
            name=asset.name or asset.symbol or 'N/A',
            quantity=qty,
            average_buy_price=avg_price,
            total_cost=cost_eur,
            current_price=price_eur,
        )
        positions.append(pos)
        posiciones.append(_position_to_dict(pos))

    posiciones.sort(key=lambda x: x['value'], reverse=True)

    snapshot = create_asset_category_snapshot(category='stocks', positions=positions)

    return {
        'total_cost': round(snapshot.total_cost, 2),
        'total_value': round(snapshot.total_value, 2),
        'total_pnl': round(snapshot.total_pnl, 2),
        'total_pnl_pct': round(snapshot.total_pnl_pct, 1),
        'holdings_count': len(posiciones),
        'positions': posiciones,
        'top_holdings': posiciones[: top_n] if top_n else posiciones,
        'holdings': holdings,
        'snapshot': snapshot,
    }


def _empty_metrics(top_n: int = None) -> Dict[str, Any]:
    return {
        'total_cost': 0.0,
        'total_value': 0.0,
        'total_pnl': 0.0,
        'total_pnl_pct': 0.0,
        'holdings_count': 0,
        'positions': [],
        'top_holdings': [],
        'holdings': [],
    }
