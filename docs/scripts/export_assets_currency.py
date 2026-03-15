"""
Exporta activos con transacciones (o en holdings) del usuario: symbol, currency, asset_id.
Para comparar entre entornos: ejecutar en local y en producción, guardar JSON, luego usar
compare_assets_currency.py para ver símbolos con distinta currency.

Uso:
  FLASK_APP=run.py python docs/scripts/export_assets_currency.py amieva91
  # En local:
  FLASK_APP=run.py python docs/scripts/export_assets_currency.py amieva91 > local_assets.json
  # En producción (mismo comando, guardar como prod_assets.json)
  # Comparar:
  python docs/scripts/compare_assets_currency.py local_assets.json prod_assets.json
"""
import sys
import json
import os
from pathlib import Path
from collections import defaultdict

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
from app.models import User, Transaction, Asset, PortfolioHolding

app = create_app()


def run(username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'error': f'Usuario no encontrado: {username}'}
        user_id = user.id

        # Asset IDs que tienen transacciones o holdings para este usuario
        txn_asset_ids = (
            Transaction.query.filter_by(user_id=user_id)
            .filter(Transaction.asset_id.isnot(None))
            .with_entities(Transaction.asset_id)
            .distinct()
            .all()
        )
        holding_asset_ids = (
            PortfolioHolding.query.filter_by(user_id=user_id)
            .with_entities(PortfolioHolding.asset_id)
            .distinct()
            .all()
        )
        asset_ids = set(a[0] for a in txn_asset_ids) | set(a[0] for a in holding_asset_ids)

        # Por cada asset: symbol, currency, id y monedas usadas en transacciones
        assets = []
        for aid in sorted(asset_ids):
            asset = Asset.query.get(aid)
            if not asset:
                assets.append({
                    'asset_id': aid,
                    'symbol': None,
                    'currency': None,
                    'note': 'asset_not_found'
                })
                continue
            # Monedas que aparecen en transacciones de este asset
            txns = Transaction.query.filter_by(user_id=user_id, asset_id=aid).all()
            currencies_in_txns = list(set(t.currency or 'EUR' for t in txns))
            assets.append({
                'asset_id': asset.id,
                'symbol': asset.symbol,
                'currency': (asset.currency or 'EUR').strip() or 'EUR',
                'transaction_count': len(txns),
                'currencies_in_transactions': sorted(currencies_in_txns),
                'currency_mismatch': len(currencies_in_txns) > 1 or (currencies_in_txns and (asset.currency or 'EUR').strip() not in currencies_in_txns),
            })

        return {
            'username': username,
            'env': os.environ.get('FLASK_ENV', 'unknown'),
            'assets': assets,
            'by_symbol': {a['symbol']: a for a in assets if a['symbol']},
        }


if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'amieva91'
    result = run(name)
    if 'error' in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)
    # Salida compacta para fácil diff
    print(json.dumps(result, indent=2, default=str))
