"""
Compara los componentes de las métricas globales (Valor Real Cuenta, P&L No Realizado,
Dividendos, Apalancamiento) para un usuario. Ejecutar en LOCAL y en PRODUCCIÓN y comparar
los dos outputs para encontrar por qué los mismos CSV dan datos distintos.

Uso (desde raíz del proyecto):
  FLASK_APP=run.py python docs/scripts/compare_metrics_envs.py amieva91

Salida: JSON en stdout (redirigir a archivo y diff, ej. compare_metrics_envs.py amieva91 > local.json)
"""
import sys
import json
import os
from pathlib import Path

# Raíz del proyecto (para importar app)
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
from app.models import User, Transaction, PortfolioHolding, Asset
from app.services.currency_service import convert_to_eur, get_exchange_rates, get_cache_info

app = create_app()


def run(username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'error': f'Usuario no encontrado: {username}'}
        user_id = user.id

        # 1) Transacciones por tipo (depósitos, retiradas, dividendos, comisiones)
        def tx_summary(tx_type_list, label):
            q = Transaction.query.filter_by(user_id=user_id).filter(
                Transaction.transaction_type.in_(tx_type_list)
            ).all()
            total_eur = sum(convert_to_eur(abs(t.amount), t.currency) for t in q)
            by_currency = {}
            for t in q:
                c = t.currency or 'EUR'
                by_currency[c] = by_currency.get(c, 0) + abs(float(t.amount))
            return {'count': len(q), 'total_eur': round(total_eur, 2), 'by_currency': by_currency}

        deposits = tx_summary(['DEPOSIT'], 'deposits')
        withdrawals = tx_summary(['WITHDRAWAL'], 'withdrawals')
        dividends = tx_summary(['DIVIDEND'], 'dividends')
        fees = tx_summary(['FEE', 'COMMISSION'], 'fees')

        # Lista de cada dividendo (para ver duplicados o diferencias de conversión)
        div_txns = Transaction.query.filter_by(
            user_id=user_id, transaction_type='DIVIDEND'
        ).order_by(Transaction.transaction_date, Transaction.id).all()
        dividends_detail = []
        for t in div_txns:
            amt_eur = convert_to_eur(abs(t.amount), t.currency)
            dividends_detail.append({
                'id': t.id,
                'date': str(t.transaction_date),
                'amount': float(t.amount),
                'currency': t.currency or 'EUR',
                'amount_eur': round(amt_eur, 4),
                'asset_id': t.asset_id,
            })

        # 2) P&L Realizado (FIFO) - solo el total para comparar
        from app.services.metrics.basic_metrics import BasicMetrics
        pl_realized_data = BasicMetrics.calculate_pl_realized(user_id, None, None)
        pl_realized = pl_realized_data['realized_pl']

        # 3) Holdings: coste, precio actual, valor en EUR, P&L no realizado
        holdings_raw = PortfolioHolding.query.filter_by(
            user_id=user_id
        ).filter(PortfolioHolding.quantity > 0).all()
        holdings_detail = []
        total_cost_eur = 0.0
        total_value_eur = 0.0
        for h in holdings_raw:
            a = h.asset
            if not a:
                continue
            cost_eur = convert_to_eur(h.total_cost, a.currency)
            total_cost_eur += cost_eur
            if a.current_price is not None:
                value_local = h.quantity * a.current_price
                value_eur = convert_to_eur(value_local, a.currency)
            else:
                value_eur = 0.0
            total_value_eur += value_eur
            pl_u = value_eur - cost_eur
            holdings_detail.append({
                'asset_id': a.id,
                'symbol': a.symbol or '',
                'isin': a.isin or '',
                'currency': a.currency or 'EUR',
                'quantity': float(h.quantity),
                'total_cost_local': float(h.total_cost),
                'cost_eur': round(cost_eur, 4),
                'current_price': a.current_price,
                'value_eur': round(value_eur, 4),
                'pl_unrealized_eur': round(pl_u, 4),
            })
        pl_unrealized = total_value_eur - total_cost_eur

        # 4) Valor Real Cuenta y Apalancamiento (fórmula del dashboard)
        account_value = (
            deposits['total_eur'] - withdrawals['total_eur'] +
            pl_realized + pl_unrealized + dividends['total_eur'] - fees['total_eur']
        )
        account_value_without_u = (
            deposits['total_eur'] - withdrawals['total_eur'] +
            pl_realized + dividends['total_eur'] - fees['total_eur']
        )
        leverage = max(0, total_cost_eur - account_value_without_u)

        # 5) Tasas de cambio (para ver si difieren entre entornos)
        rates = get_exchange_rates()
        cache_info = get_cache_info()
        rates_subset = {k: round(v, 6) for k, v in sorted(rates.items()) if k in ['USD', 'GBP', 'HKD', 'PLN', 'AUD', 'GBX', 'EUR']}

        out = {
            'username': username,
            'user_id': user_id,
            'transactions': {
                'deposits': deposits,
                'withdrawals': withdrawals,
                'dividends': dividends,
                'dividends_detail': dividends_detail,
                'fees': fees,
            },
            'pl_realized': round(pl_realized, 2),
            'holdings': {
                'count': len(holdings_detail),
                'total_cost_eur': round(total_cost_eur, 2),
                'total_value_eur': round(total_value_eur, 2),
                'pl_unrealized': round(pl_unrealized, 2),
                'detail': holdings_detail,
            },
            'metrics': {
                'total_account_value': round(account_value, 2),
                'leverage': round(leverage, 2),
            },
            'exchange_rates': rates_subset,
            'cache_info': {k: str(v) if hasattr(v, 'isoformat') else v for k, v in cache_info.items()},
        }
        return out


def run_transactions(username):
    """Solo transacciones: conteo por tipo y lista comparable (date, type, amount, currency, isin, qty, price)."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'error': f'Usuario no encontrado: {username}'}
        user_id = user.id
        all_tx = (
            Transaction.query.filter_by(user_id=user_id)
            .order_by(Transaction.transaction_date, Transaction.id)
            .all()
        )
        # Conteo por tipo
        by_type = {}
        for t in all_tx:
            tt = t.transaction_type or 'UNKNOWN'
            by_type[tt] = by_type.get(tt, 0) + 1
        # Total EUR por tipo
        total_eur_by_type = {}
        for t in all_tx:
            tt = t.transaction_type or 'UNKNOWN'
            if tt not in total_eur_by_type:
                total_eur_by_type[tt] = 0.0
            total_eur_by_type[tt] += convert_to_eur(abs(t.amount), t.currency or 'EUR')
        # Lista comparable: sin id (difieren entre entornos), con isin para identificar activo
        rows = []
        for t in all_tx:
            isin = ''
            if t.asset_id:
                a = Asset.query.get(t.asset_id)
                if a:
                    isin = (a.isin or '')[:20]
            rows.append({
                'date': str(t.transaction_date)[:10] if t.transaction_date else '',
                'type': t.transaction_type or '',
                'amount': round(float(t.amount), 4),
                'currency': (t.currency or 'EUR').strip(),
                'isin': isin,
                'quantity': round(float(t.quantity or 0), 6),
                'price': round(float(t.price or 0), 6),
            })
        return {
            'username': username,
            'total_count': len(all_tx),
            'count_by_type': by_type,
            'total_eur_by_type': {k: round(v, 2) for k, v in total_eur_by_type.items()},
            'rows': rows,
        }


def run_transactions_summary(username):
    """Solo conteos y totales por tipo (sin lista de filas)."""
    data = run_transactions(username)
    if 'error' in data:
        return data
    return {
        'username': data['username'],
        'total_count': data['total_count'],
        'count_by_type': data['count_by_type'],
        'total_eur_by_type': data['total_eur_by_type'],
    }


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    name = args[0] if args else 'amieva91'
    summary_only = '--summary' in sys.argv
    transactions_only = '--transactions' in sys.argv
    transactions_summary_only = '--transactions-summary' in sys.argv
    if transactions_summary_only:
        result = run_transactions_summary(name)
        if 'error' in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    if transactions_only:
        result = run_transactions(name)
        if 'error' in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)
    result = run(name)
    if 'error' in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)
    if summary_only:
        m = result['metrics']
        t = result['transactions']
        h = result['holdings']
        print(json.dumps({
            'total_account_value': m['total_account_value'],
            'pl_unrealized': h['pl_unrealized'],
            'dividends_total_eur': t['dividends']['total_eur'],
            'dividends_count': t['dividends']['count'],
            'leverage': m['leverage'],
            'deposits': t['deposits']['total_eur'],
            'withdrawals': t['withdrawals']['total_eur'],
            'pl_realized': result['pl_realized'],
            'fees': t['fees']['total_eur'],
        }, indent=2))
    else:
        print(json.dumps(result, indent=2, default=str))
