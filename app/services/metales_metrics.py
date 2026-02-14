"""Métricas para módulo Metales (Commodity).
Precios Yahoo en USD/oz troy; cantidad interna en gramos.
1 oz troy = 31.1035 g.
"""
from typing import Dict, List, Any
from app.models import PortfolioHolding, Asset

OZ_TROY_TO_G = 31.1035


def get_metales_holdings(user_id: int):
    """Holdings de metales (asset_type Commodity)"""
    return (
        PortfolioHolding.query
        .filter(PortfolioHolding.user_id == user_id)
        .filter(PortfolioHolding.quantity > 0)
        .join(PortfolioHolding.asset)
        .filter(Asset.asset_type == 'Commodity')
        .all()
    )


def compute_metales_metrics(user_id: int) -> Dict[str, Any]:
    """Metricas del modulo Metales: capital, valor, P&L, posiciones"""
    from app.services.currency_service import convert_to_eur

    holdings = get_metales_holdings(user_id)
    if not holdings:
        return _empty_metrics()

    capital_invertido = 0.0
    valor_total = 0.0
    posiciones = []

    for h in holdings:
        asset = h.asset
        if not asset:
            continue
        qty = h.quantity or 0
        cost = h.total_cost or 0
        # Metales: transacciones manuales en EUR; coste ya en EUR
        cost_eur = cost if asset.asset_type == 'Commodity' else convert_to_eur(cost, asset.currency)
        capital_invertido += cost_eur

        # Precio Yahoo: USD/oz troy. Convertir a valor EUR para qty en gramos
        price_usd_per_oz = asset.current_price or h.current_price or 0
        if price_usd_per_oz:
            oz_from_g = qty / OZ_TROY_TO_G
            value_usd = oz_from_g * price_usd_per_oz
            value_eur = convert_to_eur(value_usd, 'USD')
            price_eur_per_g = convert_to_eur(price_usd_per_oz / OZ_TROY_TO_G, 'USD')  # Para mostrar
        else:
            value_eur = cost_eur
            price_eur_per_g = 0
        valor_total += value_eur

        pl = value_eur - cost_eur
        pl_pct = (pl / cost_eur * 100) if cost_eur > 0 else 0
        avg_price = float(h.average_buy_price) if h.average_buy_price else (cost_eur / qty if qty else 0)

        posiciones.append({
            'holding': h,
            'asset': asset,
            'symbol': asset.symbol,
            'name': asset.name,
            'quantity': qty,
            'average_buy_price': avg_price,
            'cost': cost_eur,
            'value': value_eur,
            'price': price_eur_per_g,  # EUR/g para mostrar
            'pl': pl,
            'pl_pct': pl_pct,
        })

    pl_total = valor_total - capital_invertido
    pl_pct_total = (pl_total / capital_invertido * 100) if capital_invertido > 0 else 0

    return {
        'capital_invertido': capital_invertido,
        'valor_total': valor_total,
        'pl_total': pl_total,
        'pl_pct_total': pl_pct_total,
        'posiciones': posiciones,
        'holdings': holdings,
    }


def _empty_metrics() -> Dict[str, Any]:
    return {
        'capital_invertido': 0.0,
        'valor_total': 0.0,
        'pl_total': 0.0,
        'pl_pct_total': 0.0,
        'posiciones': [],
        'holdings': [],
    }
