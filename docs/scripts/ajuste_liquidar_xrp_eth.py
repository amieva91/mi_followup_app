#!/usr/bin/env python3
"""
Liquidar posiciones XRP y ETH (ajuste manual).
El usuario ya no tiene esas monedas en Revolut - añade SELL para cerrar las posiciones.

Uso:
  python -c "
  import sys; sys.path.insert(0, '.')
  from app import create_app
  app = create_app()
  with app.app_context():
      exec(open('docs/scripts/ajuste_liquidar_xrp_eth.py').read())
  "
"""
from datetime import datetime
from app import db
from app.models import Asset, Transaction, PortfolioHolding, Broker, BrokerAccount

ADJUST_DATE = datetime(2026, 2, 12, 12, 0, 0)  # Fecha de liquidación

def liquidate(symbol):
    revolut = Broker.query.filter(Broker.name.ilike('%revolut%')).first()
    if not revolut:
        print(f"❌ {symbol}: No broker Revolut")
        return False

    asset = Asset.query.filter(Asset.symbol == symbol, Asset.asset_type == 'Crypto').first()
    if not asset:
        print(f"❌ {symbol}: Asset no encontrado")
        return False

    # Buscar holding en cuenta Revolut
    accounts = BrokerAccount.query.filter_by(broker_id=revolut.id, is_active=True).all()
    holding = None
    for acc in accounts:
        h = PortfolioHolding.query.filter_by(
            user_id=acc.user_id, account_id=acc.id, asset_id=asset.id
        ).filter(PortfolioHolding.quantity > 0).first()
        if h:
            holding = h
            break
    if not holding:
        print(f"⏭️  {symbol}: Sin posición en Revolut (ya liquidado)")
        return True

    account = BrokerAccount.query.get(holding.account_id)
    user_id = holding.user_id
    sell_qty = holding.quantity
    sell_price = holding.average_buy_price or 0.5  # fallback
    amount = sell_qty * sell_price

    txn = Transaction(
        user_id=user_id,
        account_id=account.id,
        asset_id=asset.id,
        transaction_type='SELL',
        transaction_date=ADJUST_DATE,
        settlement_date=ADJUST_DATE.date(),
        quantity=sell_qty,
        price=sell_price,
        amount=amount,
        currency='EUR',
        commission=0.0,
        fees=0.0,
        tax=0.0,
        notes=f'Ajuste manual: liquidación - ya no se dispone de {symbol} en Revolut',
        source='MANUAL'
    )
    db.session.add(txn)
    db.session.delete(holding)
    print(f"✅ {symbol}: SELL {sell_qty:.6f} @ {sell_price:.4f} EUR - posición cerrada")
    return True

def run():
    print("Liquidando XRP y ETH...")
    liquidate('XRP')
    liquidate('ETH')
    db.session.commit()
    print("\n✅ Ajustes aplicados")

run()
