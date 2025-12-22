#!/usr/bin/env python3
"""
Simulación de importación de depósitos para diagnosticar problemas
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.broker import Broker, BrokerAccount
from app.services.parsers.ibkr_parser import IBKRParser
from app.services.metrics.basic_metrics import BasicMetrics
from app.services.currency_service import convert_to_eur

app = create_app()

with app.app_context():
    print("="*80)
    print("SIMULACIÓN: Diagnóstico de Depósitos IBKR")
    print("="*80)
    print("")
    
    # 1. Obtener cuenta IBKR
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
    
    print(f"📊 Cuenta: {account.account_name} (ID: {account_id}, User: {user_id})")
    print("")
    
    # 2. Verificar depósitos actuales en DB
    print("="*80)
    print("1. DEPÓSITOS ACTUALES EN BASE DE DATOS")
    print("="*80)
    
    db_deposits = Transaction.query.filter_by(
        user_id=user_id,
        account_id=account_id,
        transaction_type='DEPOSIT'
    ).order_by(Transaction.transaction_date).all()
    
    print(f"   Total depósitos en DB: {len(db_deposits)}")
    
    total_db_eur = 0.0
    for dep in db_deposits:
        amount_eur = convert_to_eur(dep.amount, dep.currency)
        total_db_eur += amount_eur
        print(f"   - {dep.transaction_date.date()} | {dep.amount:>12,.2f} {dep.currency:3} ({amount_eur:>12,.2f} EUR) | Source: {dep.source}")
    
    print(f"\n   Total en DB: {total_db_eur:>12,.2f} EUR")
    print("")
    
    # 3. Calcular depósitos usando BasicMetrics (como lo hace el dashboard)
    print("="*80)
    print("2. CÁLCULO DE DEPÓSITOS USANDO BasicMetrics (como en dashboard)")
    print("="*80)
    
    account_components = BasicMetrics.calculate_total_account_value(user_id)
    deposits_from_metrics = account_components.get('deposits', 0)
    
    print(f"   Depósitos según BasicMetrics: {deposits_from_metrics:>12,.2f} EUR")
    print("")
    
    # 4. Verificar si hay diferencia
    print("="*80)
    print("3. COMPARACIÓN")
    print("="*80)
    
    difference = deposits_from_metrics - total_db_eur
    print(f"   Total DB (suma directa):     {total_db_eur:>12,.2f} EUR")
    print(f"   Total BasicMetrics:          {deposits_from_metrics:>12,.2f} EUR")
    print(f"   Diferencia:                  {difference:>12,.2f} EUR")
    
    if abs(difference) > 0.01:
        print(f"\n   ⚠️  HAY DIFERENCIA entre DB y BasicMetrics")
    else:
        print(f"\n   ✅ Coinciden")
    print("")
    
    # 5. Verificar depósitos de otras cuentas
    print("="*80)
    print("4. DEPÓSITOS EN OTRAS CUENTAS DEL MISMO USUARIO")
    print("="*80)
    
    all_deposits = Transaction.query.filter_by(
        user_id=user_id,
        transaction_type='DEPOSIT'
    ).order_by(Transaction.transaction_date).all()
    
    deposits_by_account = {}
    for dep in all_deposits:
        acc_id = dep.account_id
        if acc_id not in deposits_by_account:
            deposits_by_account[acc_id] = []
        deposits_by_account[acc_id].append(dep)
    
    for acc_id, deps in deposits_by_account.items():
        acc = BrokerAccount.query.get(acc_id)
        acc_name = acc.account_name if acc else f"Account ID {acc_id}"
        broker_name = acc.broker.name if acc and acc.broker else "Unknown"
        
        total_acc = sum(convert_to_eur(d.amount, d.currency) for d in deps)
        print(f"   {acc_name} ({broker_name}): {len(deps)} depósitos, Total: {total_acc:>12,.2f} EUR")
        
        if acc_id == account_id:
            print(f"      ← Esta es la cuenta IBKR actual")
    
    print("")
    
    # 6. Verificar si BasicMetrics incluye todas las cuentas o solo una
    print("="*80)
    print("5. VERIFICACIÓN DE CÁLCULO DE BasicMetrics")
    print("="*80)
    
    # Verificar el código de BasicMetrics para ver cómo calcula
    all_accounts_deposits = Transaction.query.filter_by(
        user_id=user_id,
        transaction_type='DEPOSIT'
    ).all()
    
    total_all_accounts = sum(convert_to_eur(d.amount, d.currency) for d in all_accounts_deposits)
    
    print(f"   Total depósitos en TODAS las cuentas: {total_all_accounts:>12,.2f} EUR")
    print(f"   Total según BasicMetrics:              {deposits_from_metrics:>12,.2f} EUR")
    
    if abs(total_all_accounts - deposits_from_metrics) < 0.01:
        print(f"\n   ✅ BasicMetrics incluye todas las cuentas")
    else:
        print(f"\n   ⚠️  BasicMetrics NO incluye todas las cuentas")
        print(f"      Diferencia: {total_all_accounts - deposits_from_metrics:>12,.2f} EUR")
    
    print("")
    print("="*80)
    print("CONCLUSIÓN")
    print("="*80)
    
    if abs(total_db_eur - deposits_from_metrics) > 0.01:
        print(f"⚠️  PROBLEMA DETECTADO:")
        print(f"   Los depósitos en la cuenta IBKR no coinciden con BasicMetrics")
        print(f"   Esto explica por qué no se muestran en el dashboard")
    else:
        print(f"✅ Los cálculos coinciden")
        print(f"   Si no se muestran en el dashboard, el problema está en el template o en otra parte")

