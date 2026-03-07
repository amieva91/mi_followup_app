"""
Script para eliminar brokers no deseados del catálogo.
Mantiene solo: IBKR, DeGiro, Manual, Revolut, Commodities.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Broker, BrokerAccount, Transaction, PortfolioHolding
from app.models.transaction import CashFlow
from app.models.metrics import PortfolioMetrics

BROKER_WHITELIST = {'IBKR', 'DeGiro', 'Manual', 'Revolut', 'Commodities'}


def _delete_account_cascade(account_id):
    """Elimina cuenta y datos relacionados (mismo orden que account_delete)"""
    PortfolioMetrics.query.filter_by(account_id=account_id).delete()
    CashFlow.query.filter_by(account_id=account_id).delete()
    Transaction.query.filter_by(account_id=account_id).delete()
    PortfolioHolding.query.filter_by(account_id=account_id).delete()
    BrokerAccount.query.filter_by(id=account_id).delete()


def cleanup_brokers():
    app = create_app(os.environ.get('FLASK_ENV') or 'default')
    with app.app_context():
        all_brokers = Broker.query.all()
        to_delete = [b for b in all_brokers if b.name not in BROKER_WHITELIST]

        if not to_delete:
            print("✅ No hay brokers que eliminar. Todos están en la whitelist.")
            return

        print(f"Brokers a eliminar ({len(to_delete)}):")
        for b in to_delete:
            accounts = BrokerAccount.query.filter_by(broker_id=b.id).all()
            print(f"  - {b.name} (id={b.id}, cuentas={len(accounts)})")

        deleted = 0
        skipped = 0
        for b in to_delete:
            accounts = BrokerAccount.query.filter_by(broker_id=b.id).all()
            if accounts:
                print(f"  ⏭️  {b.name} tiene {len(accounts)} cuenta(s) - OMITIDO (no se borran cuentas)")
                skipped += 1
                continue
            db.session.delete(b)
            deleted += 1
            print(f"  ✅ Broker eliminado: {b.name}")

        db.session.commit()
        print(f"\n✅ {deleted} broker(s) eliminados. {skipped} omitidos (tenían cuentas).")


if __name__ == '__main__':
    cleanup_brokers()
