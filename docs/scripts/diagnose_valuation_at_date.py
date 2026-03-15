"""
Diagnóstico de valoración a una fecha: exporta orden de transacciones y posiciones
para comparar entre entornos (local vs producción) y localizar divergencias.

Uso:
  FLASK_APP=run.py python docs/scripts/diagnose_valuation_at_date.py amieva91 [YYYY-MM-DD]

Salida JSON:
  - transactions_ordered: lista de transacciones hasta la fecha (orden proceso: date, id)
  - cash_balance_eur: saldo de efectivo en EUR tras replay
  - holdings: posiciones por activo (quantity, average_buy_price, value_eur)
  - total_value_eur: cash_balance + sum(holdings value)
"""
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal

try:
    _root = Path(__file__).resolve().parents[2]
except IndexError:
    _root = Path(os.getcwd())
if not (_root / 'app').is_dir():
    for cand in [os.environ.get('PYTHONPATH'), os.getcwd()]:
        if cand:
            p = Path(cand).resolve()
            if (p / 'app').is_dir():
                _root = p
                break
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app import create_app
from app.models import User, Transaction, Asset
from app.services.fifo_calculator import FIFOCalculator
from app.services.currency_service import convert_to_eur

# Metales: cantidad en gramos
OZ_TROY_TO_G = 31.1035

app = create_app()


def run(username, target_date_str='2023-12-31'):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'error': f'Usuario no encontrado: {username}'}
        user_id = user.id

        target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        if target_date.time().hour == 0 and target_date.time().minute == 0:
            # Incluir todo el día: fin de día
            target_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        transactions = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date <= target_date
        ).order_by(Transaction.transaction_date, Transaction.id).all()

        # Replay igual que PortfolioValuation
        fifo_calculators = {}
        cash_balance = 0.0
        transactions_export = []

        for txn in transactions:
            asset_id = txn.asset_id if txn.asset_id else None
            symbol = txn.asset.symbol if txn.asset else (f"Asset_{asset_id}" if asset_id else None)
            row = {
                'id': txn.id,
                'transaction_date': txn.transaction_date.isoformat() if txn.transaction_date else None,
                'transaction_type': txn.transaction_type,
                'asset_id': asset_id,
                'symbol': symbol,
                'quantity': txn.quantity,
                'price': txn.price,
                'currency': txn.currency or 'EUR',
                'amount': txn.amount,
                'commission': txn.commission or 0,
                'fees': txn.fees or 0,
                'tax': txn.tax or 0,
            }

            if txn.transaction_type == 'DEPOSIT':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance += amount_eur
                row['effect_eur'] = amount_eur
            elif txn.transaction_type == 'WITHDRAWAL':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance -= amount_eur
                row['effect_eur'] = -amount_eur
            elif txn.transaction_type == 'BUY' and asset_id:
                total_cost = (txn.quantity * txn.price) + (txn.commission or 0) + (txn.fees or 0) + (txn.tax or 0)
                cost_eur = convert_to_eur(total_cost, txn.currency)
                cash_balance -= cost_eur
                row['total_cost_local'] = total_cost
                row['effect_eur'] = -cost_eur
                if asset_id not in fifo_calculators:
                    fifo_calculators[asset_id] = FIFOCalculator(symbol=symbol or f"Asset_{asset_id}")
                fifo_calculators[asset_id].add_buy(
                    quantity=txn.quantity,
                    price=txn.price,
                    date=txn.transaction_date,
                    total_cost=total_cost
                )
            elif txn.transaction_type == 'SELL' and asset_id:
                proceeds = (txn.quantity * txn.price) - (txn.commission or 0) - (txn.fees or 0) - (txn.tax or 0)
                proceeds_eur = convert_to_eur(proceeds, txn.currency)
                cash_balance += proceeds_eur
                row['proceeds_local'] = proceeds
                row['effect_eur'] = proceeds_eur
                if asset_id in fifo_calculators:
                    fifo_calculators[asset_id].add_sell(quantity=txn.quantity, date=txn.transaction_date)
            elif txn.transaction_type == 'DIVIDEND':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance += amount_eur
                row['effect_eur'] = amount_eur
            elif txn.transaction_type == 'FEE':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance -= amount_eur
                row['effect_eur'] = -amount_eur
            else:
                row['effect_eur'] = None

            transactions_export.append(row)

        # Holdings a la fecha (sin usar current_price; igual que valoración pasada)
        holdings_export = []
        holdings_value_total = 0.0
        today = datetime.now().date()
        is_today = (target_date.date() >= today)

        for asset_id, fifo in fifo_calculators.items():
            position = fifo.get_current_position()
            if position['quantity'] <= 0:
                continue
            asset = Asset.query.get(asset_id)
            if not asset:
                continue
            price = position['average_buy_price']
            current_quantity = position['quantity']
            if getattr(asset, 'asset_type', None) == 'Commodity':
                oz_from_g = current_quantity / OZ_TROY_TO_G
                value_local = current_quantity * price  # EUR (avg en EUR/g)
                value_eur = convert_to_eur(value_local, 'EUR')
            else:
                value_local = current_quantity * price
                value_eur = convert_to_eur(value_local, asset.currency)
            holdings_value_total += value_eur
            holdings_export.append({
                'asset_id': asset_id,
                'symbol': asset.symbol,
                'currency': getattr(asset, 'currency', 'EUR'),
                'quantity': round(current_quantity, 6),
                'average_buy_price': round(price, 6),
                'value_eur': round(value_eur, 2),
            })

        total_value_eur = cash_balance + holdings_value_total

        return {
            'username': username,
            'target_date': target_date_str,
            'transactions_count': len(transactions_export),
            'cash_balance_eur': round(cash_balance, 2),
            'holdings_count': len(holdings_export),
            'holdings_value_eur': round(holdings_value_total, 2),
            'total_value_eur': round(total_value_eur, 2),
            'transactions_ordered': transactions_export,
            'holdings': holdings_export,
        }


if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'amieva91'
    date_arg = sys.argv[2] if len(sys.argv) > 2 else '2023-12-31'
    result = run(name, date_arg)
    if 'error' in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)
    print(json.dumps(result, indent=2, default=str))
