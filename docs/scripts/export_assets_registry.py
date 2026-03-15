"""
Exporta el registro global de activos (tabla assets) a JSON, sin id ni precios.
Para usar en sync: en producción se actualizarán los activos que coincidan por symbol/isin.

Ejecutar en LOCAL:
  FLASK_APP=run.py python docs/scripts/export_assets_registry.py > docs/scripts/assets_registry_local.json
"""
import sys
import json
import os
from pathlib import Path
from datetime import datetime

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
from app.models import Asset

app = create_app()

# Campos a exportar (registro: identificadores y clasificación; sin precios ni id)
REGISTRY_FIELDS = [
    'symbol', 'isin', 'name', 'asset_type', 'sector', 'country', 'exchange', 'currency',
    'mic', 'yahoo_suffix', 'industry',
]


def run():
    with app.app_context():
        assets = Asset.query.order_by(Asset.symbol, Asset.id).all()
        out = []
        for a in assets:
            row = {}
            for f in REGISTRY_FIELDS:
                v = getattr(a, f, None)
                if v is not None and (f != 'symbol' or (v and str(v).strip())):
                    row[f] = v if not isinstance(v, datetime) else v.isoformat()
            if not row.get('currency'):
                row['currency'] = 'EUR'
            out.append(row)
        return {'count': len(out), 'assets': out}


if __name__ == '__main__':
    result = run()
    print(json.dumps(result, indent=2, default=str))
