"""
Diagnóstico Modified Dietz por año: imprime VI, VF, cash_flows y nº transacciones por tipo
para cada año, para local vs producción. Así se ve en qué año empieza la divergencia.

Uso: FLASK_APP=run.py python docs/scripts/diagnose_dietz_by_year.py amieva91
"""
import sys
import json
import os
from pathlib import Path
from datetime import datetime
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
from app.services.metrics.modified_dietz import ModifiedDietzCalculator

app = create_app()


def run(username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'error': f'Usuario no encontrado: {username}'}
        user_id = user.id

        yearly = ModifiedDietzCalculator.get_yearly_returns(user_id)
        # Transacciones por año y tipo
        all_tx = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.transaction_date, Transaction.id
        ).all()
        by_year_type = defaultdict(lambda: defaultdict(int))
        by_year_type_eur = defaultdict(lambda: defaultdict(float))
        from app.services.currency_service import convert_to_eur
        for t in all_tx:
            y = t.transaction_date.year if t.transaction_date else 0
            tt = t.transaction_type or 'UNKNOWN'
            by_year_type[y][tt] += 1
            by_year_type_eur[y][tt] += convert_to_eur(abs(t.amount), t.currency or 'EUR')

        out = {
            'username': username,
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
