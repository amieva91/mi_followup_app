"""Servicio para recalcular holdings (posiciones) desde transacciones"""
from app import db
from app.models import Transaction, PortfolioHolding, Asset
from app.services.fifo_calculator import FIFOCalculator


def recalculate_holdings(user_id: int, account_id: int) -> int:
    """
    Recalcula los holdings de una cuenta desde las transacciones BUY/SELL con FIFO.

    Returns:
        Número de holdings creados/actualizados
    """
    db.session.flush()

    PortfolioHolding.query.filter_by(
        user_id=user_id,
        account_id=account_id
    ).delete()

    transactions = (
        Transaction.query
        .filter_by(user_id=user_id, account_id=account_id)
        .filter(Transaction.transaction_type.in_(['BUY', 'SELL']))
        .order_by(Transaction.transaction_date)
        .all()
    )

    positions = {}
    for txn in transactions:
        if not txn.asset_id:
            continue
        if txn.asset_id not in positions:
            asset = Asset.query.get(txn.asset_id)
            symbol = asset.symbol if asset else f'Asset_{txn.asset_id}'
            positions[txn.asset_id] = FIFOCalculator(symbol=symbol)

        fifo = positions[txn.asset_id]
        if txn.transaction_type == 'BUY':
            total_cost = abs(txn.amount) + (txn.commission or 0) + (txn.fees or 0) + (txn.tax or 0)
            fifo.add_buy(
                date=txn.transaction_date,
                quantity=txn.quantity,
                price=txn.price,
                total_cost=total_cost
            )
        elif txn.transaction_type == 'SELL':
            fifo.add_sell(quantity=txn.quantity, date=txn.transaction_date)

    holdings_created = 0
    for asset_id, fifo in positions.items():
        pos = fifo.get_current_position()
        if pos['quantity'] > 0:
            holding = PortfolioHolding(
                user_id=user_id,
                account_id=account_id,
                asset_id=asset_id,
                quantity=pos['quantity'],
                average_buy_price=pos['average_buy_price'],
                total_cost=pos['total_cost'],
                first_purchase_date=pos['first_purchase_date'],
                last_transaction_date=pos['last_transaction_date']
            )
            db.session.add(holding)
            holdings_created += 1

    return holdings_created
