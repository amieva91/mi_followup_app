"""
Servicio de reconciliación de bajas de cotización.
Genera transacciones SELL automáticas para posiciones abiertas en activos delisted.
"""
from datetime import date, datetime
from typing import List, Dict, Any, Tuple, Set
from app import db
from app.models import (
    Asset, AssetRegistry, AssetDelisting,
    Transaction, BrokerAccount
)
from app.services.fifo_calculator import FIFOCalculator
from app.services.portfolio_holding_service import recalculate_holdings


def get_delisted_isins() -> Set[str]:
    """
    ISINs con baja de cotización ya efectiva (fecha <= hoy).
    Si falla la consulta, devuelve set vacío.
    """
    try:
        today = date.today()
        rows = (
            db.session.query(AssetRegistry.isin)
            .join(AssetDelisting, AssetDelisting.asset_registry_id == AssetRegistry.id)
            .filter(
                AssetDelisting.delisting_date <= today,
                AssetDelisting.delisting_type.in_(['CASH_ACQUISITION', 'BANKRUPTCY'])
            )
            .filter(AssetRegistry.isin.isnot(None))
            .distinct()
            .all()
        )
        return {r[0] for r in rows if r[0]}
    except Exception:
        return set()


def get_delisted_asset_ids() -> Set[int]:
    """
    IDs de Asset con baja de cotización ya efectiva (fecha <= hoy).
    Usar para excluir estos activos del portfolio y de la actualización de precios.
    Une Asset con AssetRegistry por ISIN y con AssetDelisting.
    Si falla la consulta (p. ej. tabla no existe en producción), devuelve set vacío para no romper la vista.
    """
    try:
        today = date.today()
        rows = (
            db.session.query(Asset.id)
            .join(AssetRegistry, Asset.isin == AssetRegistry.isin)
            .join(AssetDelisting, AssetDelisting.asset_registry_id == AssetRegistry.id)
            .filter(
                AssetDelisting.delisting_date <= today,
                AssetDelisting.delisting_type.in_(['CASH_ACQUISITION', 'BANKRUPTCY'])
            )
            .distinct()
            .all()
        )
        return {r[0] for r in rows}
    except Exception:
        return set()


def reconcile_delistings(user_id: int = None) -> Dict[str, Any]:
    """
    Para cada asset con delisting y usuarios con posición abierta,
    genera SELL automática si no existe ya.
    
    Args:
        user_id: Si se proporciona, solo procesa ese usuario. Si None, todos.
    
    Returns:
        Dict con created, skipped, errors
    """
    result = {'created': 0, 'skipped': 0, 'errors': []}

    # Obtener delistings activos (solo CASH_ACQUISITION y BANKRUPTCY)
    delistings = AssetDelisting.query.filter(
        AssetDelisting.delisting_type.in_(['CASH_ACQUISITION', 'BANKRUPTCY'])
    ).all()

    if not delistings:
        return result

    today = date.today()

    for d in delistings:
        if d.delisting_date > today:
            continue  # Aún no ha ocurrido

        # Buscar Assets que apuntan a este AssetRegistry (via ISIN)
        registry = d.asset_registry
        if not registry or not registry.isin:
            continue

        assets = Asset.query.filter_by(isin=registry.isin).all()
        for asset in assets:
            # Para cada usuario/cuenta con transacciones en este asset
            accounts_with_trades = (
                db.session.query(Transaction.user_id, Transaction.account_id)
                .filter(
                    Transaction.asset_id == asset.id,
                    Transaction.transaction_type.in_(['BUY', 'SELL'])
                )
                .distinct()
                .all()
            )

            for uid, account_id in accounts_with_trades:
                if user_id is not None and uid != user_id:
                    continue

                try:
                    created = _maybe_create_delisting_sell(
                        user_id=uid,
                        account_id=account_id,
                        asset=asset,
                        delisting=d
                    )
                    if created:
                        result['created'] += 1
                        recalculate_holdings(uid, account_id)
                    else:
                        result['skipped'] += 1
                except Exception as e:
                    result['errors'].append(f"Asset {asset.symbol} user {uid}: {str(e)}")

    db.session.commit()
    return result


def _maybe_create_delisting_sell(
    user_id: int,
    account_id: int,
    asset: Asset,
    delisting: AssetDelisting
) -> bool:
    """
    Crea SELL por delisting si el usuario tenía posición y no tiene ya SELL posterior.
    Returns True si creó la transacción.
    """
    # Obtener transacciones BUY/SELL del usuario en esta cuenta para este asset
    transactions = (
        Transaction.query
        .filter_by(user_id=user_id, account_id=account_id, asset_id=asset.id)
        .filter(Transaction.transaction_type.in_(['BUY', 'SELL']))
        .order_by(Transaction.transaction_date, Transaction.id)
        .all()
    )

    # Calcular posición al cierre del día del delisting (usando FIFO)
    delisting_dt = datetime.combine(delisting.delisting_date, datetime.min.time())
    fifo = FIFOCalculator(symbol=asset.symbol or 'Unknown')

    for txn in transactions:
        if txn.transaction_date.date() > delisting.delisting_date:
            break  # No procesar transacciones después del delisting
        if txn.transaction_type == 'BUY':
            total_cost = abs(txn.amount) + (txn.commission or 0) + (txn.fees or 0) + (txn.tax or 0)
            fifo.add_buy(
                quantity=txn.quantity,
                price=txn.price,
                date=txn.transaction_date,
                total_cost=total_cost
            )
        elif txn.transaction_type == 'SELL':
            fifo.add_sell(quantity=txn.quantity, date=txn.transaction_date)

    position = fifo.get_current_position()
    if position['quantity'] <= 0:
        return False  # No tenía posición

    # Verificar si ya existe SELL en/o después del delisting
    existing_sell = (
        Transaction.query
        .filter_by(
            user_id=user_id,
            account_id=account_id,
            asset_id=asset.id,
            transaction_type='SELL'
        )
        .filter(Transaction.transaction_date >= delisting_dt)
        .first()
    )
    if existing_sell:
        return False  # Ya hay venta

    # Crear SELL
    qty = position['quantity']
    price = delisting.delisting_price
    amount = qty * price
    desc = f"Baja de cotización ({delisting.delisting_type})"
    if delisting.notes:
        desc += f": {delisting.notes}"

    txn = Transaction(
        user_id=user_id,
        account_id=account_id,
        asset_id=asset.id,
        transaction_type='SELL',
        transaction_date=delisting_dt,
        settlement_date=delisting.delisting_date,
        quantity=qty,
        price=price,
        amount=amount,
        currency=delisting.delisting_currency,
        commission=0,
        fees=0,
        tax=0,
        description=desc,
        source='DELISTING_RECONCILIATION'
    )
    db.session.add(txn)
    return True
