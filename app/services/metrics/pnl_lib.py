"""
Librería unificada de P&L (Profit & Loss).
Fórmulas centralizadas y dataclasses para Crypto, Metales, Acciones y Portfolio.

Convención de nombres: total_cost, total_value, pnl, pnl_pct
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PositionSnapshot:
    """Una posición individual (un activo)."""

    symbol: str
    name: str
    quantity: float
    average_buy_price: float
    total_cost: float  # Coste total invertido (EUR)
    total_value: float  # quantity * price actual (EUR)
    current_price: float  # Precio unitario actual
    pnl: float  # total_value - total_cost
    pnl_pct: float  # (pnl / total_cost * 100) si total_cost > 0 else 0
    extra: dict = field(default_factory=dict)  # ej. reward_quantity, reward_value


@dataclass
class AssetCategorySnapshot:
    """Snapshot agregado de una categoría (Crypto, Metales, Stocks)."""

    category: str  # "crypto" | "metales" | "stocks"
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    positions: List[PositionSnapshot]
    extra: dict = field(default_factory=dict)  # ej. cuasi_fiat, rewards_total


@dataclass
class PortfolioSnapshot:
    """Snapshot agregado del portfolio (suma de categorías)."""

    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    categories: Dict[str, AssetCategorySnapshot]


def compute_position_pnl(
    quantity: float,
    current_price: float,
    total_cost: float,
) -> tuple[float, float, float]:
    """
    Calcula valor, P&L y P&L% de una posición.

    Fórmulas:
        value = quantity * current_price  (fallback: total_cost si no hay precio)
        pnl = value - total_cost
        pnl_pct = (pnl / total_cost * 100) si total_cost > 0 else 0

    Args:
        quantity: Cantidad de unidades
        current_price: Precio unitario actual (0 si desconocido → usa coste como valor)
        total_cost: Coste total invertido

    Returns:
        (total_value, pnl, pnl_pct)
    """
    total_value = quantity * current_price if current_price else total_cost
    pnl = total_value - total_cost
    pnl_pct = (pnl / total_cost * 100.0) if total_cost > 0 else 0.0
    return (total_value, pnl, pnl_pct)


def aggregate_positions(
    positions: List[PositionSnapshot],
) -> tuple[float, float, float, float]:
    """
    Agrega posiciones para obtener totales.

    Returns:
        (total_cost, total_value, total_pnl, total_pnl_pct)
    """
    total_cost = sum(p.total_cost for p in positions)
    total_value = sum(p.total_value for p in positions)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
    return (total_cost, total_value, total_pnl, total_pnl_pct)


def create_position_snapshot(
    symbol: str,
    name: str,
    quantity: float,
    average_buy_price: float,
    total_cost: float,
    current_price: float,
    extra: Optional[dict] = None,
) -> PositionSnapshot:
    """
    Crea un PositionSnapshot con P&L calculado.
    """
    total_value, pnl, pnl_pct = compute_position_pnl(
        quantity, current_price, total_cost
    )
    return PositionSnapshot(
        symbol=symbol,
        name=name or symbol,
        quantity=quantity,
        average_buy_price=average_buy_price,
        total_cost=total_cost,
        total_value=total_value,
        current_price=current_price or 0,
        pnl=pnl,
        pnl_pct=pnl_pct,
        extra=extra or {},
    )


def create_asset_category_snapshot(
    category: str,
    positions: List[PositionSnapshot],
    extra: Optional[dict] = None,
) -> AssetCategorySnapshot:
    """
    Crea un AssetCategorySnapshot agregando las posiciones.
    """
    total_cost, total_value, total_pnl, total_pnl_pct = aggregate_positions(
        positions
    )
    return AssetCategorySnapshot(
        category=category,
        total_cost=total_cost,
        total_value=total_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        positions=positions,
        extra=extra or {},
    )


def create_portfolio_snapshot(
    categories: Dict[str, AssetCategorySnapshot],
) -> PortfolioSnapshot:
    """
    Crea un PortfolioSnapshot sumando todas las categorías.
    """
    total_cost = sum(c.total_cost for c in categories.values())
    total_value = sum(c.total_value for c in categories.values())
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
    return PortfolioSnapshot(
        total_cost=total_cost,
        total_value=total_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        categories=categories,
    )
