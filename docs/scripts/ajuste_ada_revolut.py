#!/usr/bin/env python3
"""
Ajuste manual ADA para coincidir con saldo real de Revolut.

Objetivo final:
  - Cantidad: 3.256,911379 ADA
  - Precio medio: 0,41295 EUR

Añade una transacción SELL de la diferencia y actualiza el holding al valor exacto.
(Se usa 1 julio 2025 porque 1 julio 2024 sería antes de la primera compra de ADA)

Uso (desde la raíz del proyecto):
  flask shell
  >>> exec(open('docs/scripts/ajuste_ada_revolut.py').read())

O:
  python -c "
  import sys; sys.path.insert(0, '.')
  from app import create_app
  app = create_app()
  with app.app_context():
      exec(open('docs/scripts/ajuste_ada_revolut.py').read())
  "
"""
from datetime import datetime
from app import db
from app.models import User, BrokerAccount, Asset, Transaction, PortfolioHolding, Broker
from app.services.fifo_calculator import FIFOCalculator

# Parámetros objetivo (saldo real Revolut)
TARGET_QTY = 3256.911379
TARGET_AVG = 0.41295
TARGET_COST = TARGET_QTY * TARGET_AVG  # 1344.74 EUR aprox

# Cantidad actual según CSV (buys + rewards)
CURRENT_QTY = 3373.1926
SELL_QTY = CURRENT_QTY - TARGET_QTY  # 116.281221 ADA

# Fecha: 1 julio 2025 (2024 sería antes de la primera compra ADA)
ADJUST_DATE = datetime(2025, 7, 1, 12, 0, 0)

def run():
    # Buscar usuario con cuenta Revolut
    revolut = Broker.query.filter(Broker.name.ilike('%revolut%')).first()
    if not revolut:
        print("❌ No se encontró broker Revolut")
        return

    accounts = BrokerAccount.query.filter_by(broker_id=revolut.id, is_active=True).all()
    if not accounts:
        print("❌ No hay cuentas Revolut activas")
        return

    # Buscar asset ADA (Crypto)
    asset = Asset.query.filter(Asset.symbol == 'ADA', Asset.asset_type == 'Crypto').first()
    if not asset:
        print("❌ No se encontró asset ADA")
        return

    # Encontrar cuenta que tenga holding ADA
    holding = None
    for acc in accounts:
        h = PortfolioHolding.query.filter_by(user_id=acc.user_id, account_id=acc.id, asset_id=asset.id).first()
        if h:
            holding = h
            account = acc
            break
    if not holding:
        account = accounts[0]
        holding = PortfolioHolding.query.filter_by(user_id=account.user_id, account_id=account.id, asset_id=asset.id).first()
    user_id = account.user_id

    print(f"Usuario: {user_id}, Cuenta: {account.account_name} (id={account.id})")
    print(f"Asset ADA: id={asset.id}")
    print(f" Holding actual: qty={holding.quantity if holding else 'N/A'}, avg={holding.average_buy_price if holding else 'N/A'}")

    # Crear transacción SELL
    sell_price = TARGET_AVG
    amount = SELL_QTY * sell_price  # SELL = ingreso positivo

    txn = Transaction(
        user_id=user_id,
        account_id=account.id,
        asset_id=asset.id,
        transaction_type='SELL',
        transaction_date=ADJUST_DATE,
        settlement_date=ADJUST_DATE.date(),
        quantity=SELL_QTY,
        price=sell_price,
        amount=amount,
        currency='EUR',
        commission=0.0,
        fees=0.0,
        tax=0.0,
        notes='Ajuste manual para coincidir con saldo real Revolut (diferencia CSV vs app)',
        source='MANUAL'
    )
    db.session.add(txn)
    db.session.flush()

    # Recalcular holdings con FIFO
    transactions = Transaction.query.filter_by(
        user_id=user_id,
        account_id=account.id,
        asset_id=asset.id
    ).order_by(Transaction.transaction_date).all()

    fifo = FIFOCalculator('ADA')
    for t in transactions:
        if t.transaction_type == 'BUY':
            total_cost = abs(t.amount) + (t.commission or 0) + (t.fees or 0) + (t.tax or 0)
            fifo.add_buy(quantity=t.quantity, price=t.price, date=t.transaction_date, total_cost=total_cost)
        elif t.transaction_type == 'SELL':
            fifo.add_sell(quantity=t.quantity, date=t.transaction_date)

    pos = fifo.get_current_position()
    print(f"\n Tras FIFO: qty={pos['quantity']}, avg={pos['average_buy_price']}, cost={pos['total_cost']}")

    # Ajustar holding al valor exacto (Revolut)
    h = PortfolioHolding.query.filter_by(user_id=user_id, account_id=account.id, asset_id=asset.id).first()
    if h:
        h.quantity = TARGET_QTY
        h.average_buy_price = TARGET_AVG
        h.total_cost = TARGET_COST
        h.last_transaction_date = ADJUST_DATE.date()
        print(f" Holding actualizado a: qty={TARGET_QTY}, avg={TARGET_AVG}, cost={TARGET_COST:.2f}")
    else:
        h = PortfolioHolding(
            user_id=user_id,
            account_id=account.id,
            asset_id=asset.id,
            quantity=TARGET_QTY,
            average_buy_price=TARGET_AVG,
            total_cost=TARGET_COST,
            first_purchase_date=ADJUST_DATE.date(),
            last_transaction_date=ADJUST_DATE.date()
        )
        db.session.add(h)

    db.session.commit()
    print("\n✅ Ajuste aplicado. ADA: 3.256,911379 @ 0,41295 EUR")

run()
