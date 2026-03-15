"""
Aplica en la base de datos ACTUAL el registro de activos exportado desde local.
Actualiza por symbol (o isin si no hay symbol): currency, name, asset_type, sector, country,
exchange, mic, yahoo_suffix, industry. No toca id ni precios (current_price, last_price_update).

Ejecutar EN PRODUCCIÓN (o con DB de producción):
  FLASK_APP=run.py python docs/scripts/sync_assets_registry.py docs/scripts/assets_registry_local.json

O con ruta al JSON como primer argumento.
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

from app import create_app, db
from app.models import Asset

app = create_app()

REGISTRY_FIELDS = [
    'symbol', 'isin', 'name', 'asset_type', 'sector', 'country', 'exchange', 'currency',
    'mic', 'yahoo_suffix', 'industry',
]


def run(json_path):
    path = Path(json_path)
    if not path.exists():
        return {'error': f'No existe el archivo: {path}'}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    assets_data = data.get('assets', data) if isinstance(data, dict) else data
    if not isinstance(assets_data, list):
        return {'error': 'El JSON debe tener una lista "assets" o ser una lista'}

    with app.app_context():
        updated = 0
        skipped_no_match = 0
        errors = []
        for row in assets_data:
            symbol = (row.get('symbol') or '').strip() or None
            isin = (row.get('isin') or '').strip() or None
            if not symbol and not isin:
                skipped_no_match += 1
                continue
            q = Asset.query
            if symbol:
                q = q.filter(Asset.symbol == symbol)
            else:
                q = q.filter(Asset.isin == isin)
            targets = q.all()
            if not targets:
                skipped_no_match += 1
                continue
            for asset in targets:
                try:
                    for f in REGISTRY_FIELDS:
                        if f not in row:
                            continue
                        v = row[f]
                        if v is None or (isinstance(v, str) and not v.strip()):
                            continue
                        if f in ('sector', 'country', 'exchange', 'industry') and v is not None:
                            v = str(v).strip() or None
                        if f == 'currency' and v:
                            v = str(v).strip().upper()[:3]
                        setattr(asset, f, v)
                    updated += 1
                except Exception as e:
                    errors.append(f"{symbol or isin}: {e}")
        if errors:
            db.session.rollback()
            return {'error': 'Errores al actualizar', 'details': errors}
        db.session.commit()
        return {
            'updated': updated,
            'skipped_no_match': skipped_no_match,
            'total_in_file': len(assets_data),
        }


if __name__ == '__main__':
    json_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not json_path:
        print('Uso: FLASK_APP=run.py python sync_assets_registry.py <ruta_a_assets_registry_local.json>')
        sys.exit(1)
    result = run(json_path)
    if 'error' in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)
    print(json.dumps(result, indent=2))
    print(f"\n✅ Actualizados {result['updated']} activos. Sin coincidencia: {result['skipped_no_match']}.")
