#!/usr/bin/env python3
"""
Script para analizar depósitos de IBKR en detalle
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.broker import Broker, BrokerAccount
from app.services.parsers.ibkr_parser import IBKRParser
from datetime import datetime

app = create_app()

with app.app_context():
    # 1. Obtener cuenta IBKR del usuario
    ibkr = Broker.query.filter_by(name='IBKR').first()
    if not ibkr:
        print("❌ No se encontró el broker IBKR")
        sys.exit(1)
    
    broker_accounts = BrokerAccount.query.filter_by(broker_id=ibkr.id).all()
    if not broker_accounts:
        print("❌ No se encontraron cuentas IBKR")
        sys.exit(1)
    
    account = broker_accounts[0]
    user_id = account.user_id
    account_id = account.id
    
    print(f"📊 Analizando cuenta IBKR: {account.account_name}\n")
    
    # 2. Buscar el CSV más completo (el más antiguo que debería tener todos los depósitos)
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    csv_file = os.path.join(uploads_dir, 'U12722327_20230912_20240911.csv')
    
    if not os.path.exists(csv_file):
        print(f"❌ No se encontró el CSV: {csv_file}")
        sys.exit(1)
    
    print(f"📄 Analizando CSV: {os.path.basename(csv_file)}\n")
    
    # 3. Parsear el CSV
    parser = IBKRParser()
    parsed_data = parser.parse(csv_file)
    
    # 4. Mostrar sección de depósitos y retiros
    deposits_section = parser.sections.get('Depósitos y retiradas') or \
                      parser.sections.get('Deposits & Withdrawals')
    
    if deposits_section:
        print(f"📋 Contenido de la sección 'Depósitos y retiradas':")
        print(f"   Headers: {deposits_section.get('headers', [])}\n")
        print(f"   Filas de datos:")
        for i, row in enumerate(deposits_section.get('data', []), 1):
            print(f"   {i}. {row}")
        
        print(f"\n📊 Depósitos parseados: {len(parsed_data.get('deposits', []))}")
        for dep in parsed_data.get('deposits', []):
            date_str = dep['date'].strftime('%Y-%m-%d') if isinstance(dep['date'], datetime) else str(dep['date'])
            print(f"   - {date_str} | {dep['amount']:>12,.2f} {dep['currency']:3} | {dep.get('description', 'N/A')}")
        
        print(f"\n📊 Retiros parseados: {len(parsed_data.get('withdrawals', []))}")
        for wd in parsed_data.get('withdrawals', []):
            date_str = wd['date'].strftime('%Y-%m-%d') if isinstance(wd['date'], datetime) else str(wd['date'])
            print(f"   - {date_str} | {wd['amount']:>12,.2f} {wd['currency']:3} | {wd.get('description', 'N/A')}")
    
    # 5. Comparar con base de datos
    print(f"\n{'='*80}")
    print(f"📥 Depósitos en Base de Datos (para esta cuenta):")
    
    db_deposits = Transaction.query.filter_by(
        user_id=user_id,
        account_id=account_id,
        transaction_type='DEPOSIT'
    ).order_by(Transaction.transaction_date).all()
    
    print(f"   Total: {len(db_deposits)} depósitos\n")
    
    for dep in db_deposits:
        print(f"   - {dep.transaction_date.date()} | {dep.amount:>12,.2f} {dep.currency:3} | {dep.description}")
    
    # 6. Verificar si los depósitos del CSV están en la DB
    print(f"\n{'='*80}")
    print(f"🔍 Verificando coincidencias:\n")
    
    csv_deposits = parsed_data.get('deposits', [])
    for csv_dep in csv_deposits:
        csv_date = csv_dep['date'] if isinstance(csv_dep['date'], datetime) else datetime.strptime(csv_dep['date'], '%Y-%m-%d')
        csv_amount = float(csv_dep['amount'])
        csv_currency = csv_dep['currency']
        
        # Buscar en DB
        found = False
        for db_dep in db_deposits:
            if (db_dep.transaction_date.date() == csv_date.date() and 
                abs(float(db_dep.amount) - csv_amount) < 0.01 and
                db_dep.currency == csv_currency):
                found = True
                print(f"   ✅ {csv_date.date()} | {csv_amount:>12,.2f} {csv_currency:3} - ENCONTRADO en DB")
                break
        
        if not found:
            print(f"   ❌ {csv_date.date()} | {csv_amount:>12,.2f} {csv_currency:3} - NO ENCONTRADO en DB")

