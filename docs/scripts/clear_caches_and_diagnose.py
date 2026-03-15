"""
Prueba limpiando caches: invalida cache de métricas, fuerza tasas frescas y ejecuta
el diagnóstico Dietz por año. Sirve para comprobar si las diferencias local/producción
vienen del cache de tasas.

Uso:
  FLASK_APP=run.py python docs/scripts/clear_caches_and_diagnose.py [username]

Si quieres limpiar el cache de tasas del servidor (proceso web) para que la próxima
petición use tasas nuevas: reinicia el servicio, o en flask shell:
  from app.services.currency_service import clear_rates_cache; clear_rates_cache()
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
from app.models import User, Transaction
from app.services.currency_service import get_exchange_rates, clear_rates_cache
from app.services.metrics.cache import MetricsCacheService
from app.services.metrics.modified_dietz import ModifiedDietzCalculator

app = create_app()


def run(username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'error': f'Usuario no encontrado: {username}'}
        user_id = user.id

        # 1) Limpiar cache de tasas (en este proceso; el servidor web no se ve afectado)
        clear_rates_cache()
        # 2) Forzar tasas frescas ahora (este proceso usará estas tasas para el diagnóstico)
        rates = get_exchange_rates(force_refresh=True)
        # 3) Invalidar cache de métricas del usuario para que el dashboard recalcule
        MetricsCacheService.invalidate(user_id)

        yearly = ModifiedDietzCalculator.get_yearly_returns(user_id)
        all_tx = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.transaction_date, Transaction.id
        ).all()
        from app.services.currency_service import convert_to_eur
        by_year_type = defaultdict(lambda: defaultdict(int))
        by_year_type_eur = defaultdict(lambda: defaultdict(float))
        for t in all_tx:
            y = t.transaction_date.year if t.transaction_date else 0
            tt = t.transaction_type or 'UNKNOWN'
            by_year_type[y][tt] += 1
            by_year_type_eur[y][tt] += convert_to_eur(abs(t.amount), t.currency or 'EUR')

        out = {
            'username': username,
            'cache_cleared': True,
            'exchange_rates_sample': {k: rates.get(k) for k in list(rates.keys())[:5]} if rates else None,
            'yearly_returns': [
                {
                    'year': r['year'],
                    'return_pct': r['return_pct'],
                    'absolute_gain': r['absolute_gain'],
                    'start_value': r.get('start_value', 0),
                    'end_value': r.get('end_value', 0),
                    'is_ytd': r.get('is_ytd', False),
                }
                for r in yearly
            ],
            'transactions_per_year': {
                str(y): dict(by_year_type[y]) for y in sorted(by_year_type.keys())
            },
            'transactions_eur_per_year': {
                str(y): {k: round(v, 2) for k, v in by_year_type_eur[y].items()}
                for y in sorted(by_year_type_eur.keys())
            },
        }
        return out


if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'amieva91'
    result = run(name)
    if 'error' in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)
    print(json.dumps(result, indent=2, default=str))
