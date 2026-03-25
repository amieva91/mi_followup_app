"""Métricas para módulo Metales (Commodity).
Precios Yahoo en USD/oz troy; cantidad interna en gramos.
1 oz troy = 31.1035 g.
Usa pnl_lib para fórmulas unificadas de P&L.
"""
from typing import Dict, List, Any

from app.services.metrics.pnl_lib import (
    create_position_snapshot,
    create_asset_category_snapshot,
)

OZ_TROY_TO_G = 31.1035


def get_metales_holdings(user_id: int):
    """Holdings de metales (asset_type Commodity)"""
    from app.models import PortfolioHolding, Asset

    return (
        PortfolioHolding.query
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(PortfolioHolding.asset)
        .filter(Asset.asset_type == 'Commodity')
        .all()
    )


def _position_to_dict(ps, holding=None, asset=None) -> Dict[str, Any]:
    """Convierte PositionSnapshot a dict para templates (retrocompatibilidad)."""
    d = {
        'symbol': ps.symbol,
        'name': ps.name,
        'quantity': ps.quantity,
        'average_buy_price': ps.average_buy_price,
        'cost': ps.total_cost,
        'value': ps.total_value,
        'price': ps.current_price,  # EUR/g para mostrar
        'pl': ps.pnl,
        'pl_pct': ps.pnl_pct,
    }
    # CRÍTICO: Este dict se usa también en cachés JSON (dashboard_summary_cache),
    # así que NO puede contener objetos SQLAlchemy (holding/asset).
    if asset is not None:
        d['asset_id'] = asset.id
    return d


def compute_metales_metrics(user_id: int) -> Dict[str, Any]:
    """Métricas del módulo Metales usando pnl_lib. Capital, valor, P&L, posiciones."""
    from app.services.currency_service import convert_to_eur

    holdings = get_metales_holdings(user_id)
    if not holdings:
        return _empty_metrics()

    positions = []
    posiciones = []

    for h in holdings:
        asset = h.asset
        if not asset:
            continue
        qty = h.quantity or 0
        cost = h.total_cost or 0
        cost_eur = cost if asset.asset_type == 'Commodity' else convert_to_eur(cost, asset.currency)

        # Precio Yahoo: USD/oz troy. Convertir a valor EUR para qty en gramos
        price_usd_per_oz = asset.current_price or h.current_price or 0
        if price_usd_per_oz:
            oz_from_g = qty / OZ_TROY_TO_G
            value_usd = oz_from_g * price_usd_per_oz
            value_eur = convert_to_eur(value_usd, 'USD')
            price_eur_per_g = convert_to_eur(price_usd_per_oz / OZ_TROY_TO_G, 'USD')
        else:
            value_eur = cost_eur
            price_eur_per_g = 0

        avg_price = float(h.average_buy_price) if h.average_buy_price else (cost_eur / qty if qty else 0)

        pos = create_position_snapshot(
            symbol=asset.symbol or '',
            name=asset.name or asset.symbol or '',
            quantity=qty,
            average_buy_price=avg_price,
            total_cost=cost_eur,
            current_price=price_eur_per_g,
        )
        positions.append(pos)
        posiciones.append(_position_to_dict(pos, holding=h, asset=asset))

    snapshot = create_asset_category_snapshot(category='metales', positions=positions)

    return {
        'total_cost': snapshot.total_cost,
        'total_value': snapshot.total_value,
        'total_pnl': snapshot.total_pnl,
        'total_pnl_pct': snapshot.total_pnl_pct,
        'capital_invertido': snapshot.total_cost,
        'valor_total': snapshot.total_value,
        'pl_total': snapshot.total_pnl,
        'pl_pct_total': snapshot.total_pnl_pct,
        'posiciones': posiciones,
        'holdings': holdings,
        'snapshot': snapshot,
    }


def _empty_metrics() -> Dict[str, Any]:
    snapshot = create_asset_category_snapshot(category='metales', positions=[])
    return {
        'total_cost': 0.0,
        'total_value': 0.0,
        'total_pnl': 0.0,
        'total_pnl_pct': 0.0,
        'capital_invertido': 0.0,
        'valor_total': 0.0,
        'pl_total': 0.0,
        'pl_pct_total': 0.0,
        'posiciones': [],
        'holdings': [],
        'snapshot': snapshot,
    }
