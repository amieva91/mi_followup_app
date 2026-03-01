"""
Servicio para reflejar DEPOSIT/WITHDRAWAL del broker como ingreso/gasto.
Solo cuentas IBKR y DeGiro (Stock/ETF).
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from sqlalchemy import extract
from app import db
from app.models import Transaction, BrokerAccount, Broker
from app.services.currency_service import convert_to_eur

def _broker_account_ids(user_id):
    """IDs de cuentas de brokers IBKR y DeGiro (Stock/ETF) del usuario.
    Match case-insensitive: IBKR, DeGiro, Degiro, DEGIRO, etc."""
    return db.session.query(BrokerAccount.id).join(Broker, BrokerAccount.broker_id == Broker.id).filter(
        BrokerAccount.user_id == user_id,
        db.or_(
            db.func.upper(Broker.name) == 'IBKR',
            db.func.lower(Broker.name).like('%degiro%')
        )
    ).all()


def get_broker_withdrawals_by_month(user_id, year, month):
    """Suma de WITHDRAWAL (broker→banco) en EUR para el mes. Es ingreso."""
    account_ids = [r[0] for r in _broker_account_ids(user_id)]
    if not account_ids:
        return 0.0

    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = (date(year, month, 28) + relativedelta(months=1)) - relativedelta(days=1)

    txns = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.account_id.in_(account_ids),
        Transaction.transaction_type == 'WITHDRAWAL',
        extract('year', Transaction.transaction_date) == year,
        extract('month', Transaction.transaction_date) == month
    ).all()

    total = 0.0
    for t in txns:
        total += convert_to_eur(abs(t.amount), t.currency)
    return round(total, 2)


def get_broker_deposits_by_month(user_id, year, month):
    """Dict {broker_name: amount_eur} para DEPOSIT en el mes. Son gastos."""
    account_ids = db.session.query(BrokerAccount.id, Broker.name).join(
        Broker, BrokerAccount.broker_id == Broker.id
    ).filter(
        BrokerAccount.user_id == user_id,
        db.or_(
            db.func.upper(Broker.name) == 'IBKR',
            db.func.lower(Broker.name).like('%degiro%')
        )
    ).all()
    if not account_ids:
        return {}

    acc_to_broker = {r[0]: r[1] for r in account_ids}

    txns = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.account_id.in_(acc_to_broker.keys()),
        Transaction.transaction_type == 'DEPOSIT',
        extract('year', Transaction.transaction_date) == year,
        extract('month', Transaction.transaction_date) == month
    ).all()

    result = {}
    for t in txns:
        broker = acc_to_broker.get(t.account_id, 'Otro')
        amt = convert_to_eur(abs(t.amount), t.currency)
        result[broker] = result.get(broker, 0) + amt
    return {k: round(v, 2) for k, v in result.items()}


def get_broker_deposits_total_by_month(user_id, year, month):
    """Total de DEPOSIT en EUR para el mes (suma de todos los brokers)."""
    d = get_broker_deposits_by_month(user_id, year, month)
    return sum(d.values())
