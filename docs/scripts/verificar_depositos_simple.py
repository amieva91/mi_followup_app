#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.broker import Broker, BrokerAccount
from app.services.currency_service import convert_to_eur

app = create_app()
with app.app_context():
    ibkr = Broker.query.filter_by(name='IBKR').first()
    if ibkr:
        accounts = BrokerAccount.query.filter_by(broker_id=ibkr.id).all()
        for acc in accounts:
            deps = Transaction.query.filter_by(user_id=acc.user_id, account_id=acc.id, transaction_type='DEPOSIT').all()
            total = sum(convert_to_eur(d.amount, d.currency) for d in deps)
            print(f"IBKR Account {acc.id}: {len(deps)} deposits, Total: {total:,.2f} EUR")
    
    # Total del usuario
    if accounts:
        user_id = accounts[0].user_id
        all_deps = Transaction.query.filter_by(user_id=user_id, transaction_type='DEPOSIT').all()
        total_all = sum(convert_to_eur(d.amount, d.currency) for d in all_deps)
        print(f"TOTAL user {user_id}: {len(all_deps)} deposits, Total: {total_all:,.2f} EUR")

