#!/usr/bin/env python3
"""
Diagnóstico de detección de duplicados en depósitos
Simula el proceso de importación para entender por qué se saltan
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.broker import Broker, BrokerAccount
from app.services.parsers.ibkr_parser import IBKRParser
from app.services.importer_v2 import parse_datetime

app = create_app()

with app.app_context():
    print("="*80)
    print("DIAGNÓSTICO: Detección de Duplicados en Depósitos")
    print("="*80)
    print("")
    
    # 1. Obtener cuenta IBKR
    ibkr = Broker.query.filter_by(name='IBKR').first()
    account = BrokerAccount.query.filter_by(broker_id=ibkr.id).first()
    user_id = account.user_id
    account_id = account.id
    
    print(f"📊 Cuenta: {account.account_name} (ID: {account_id}, User: {user_id})")
    print("")
    
    # 2. Crear snapshot como lo hace el importer
    print("="*80)
    print("1. CREAR SNAPSHOT DE TRANSACCIONES EXISTENTES (como importer)")
    print("="*80)
    
    existing_transactions_snapshot = set()
    
    existing = Transaction.query.filter_by(
        user_id=user_id,
        account_id=account_id
    ).all()
    
    print(f"   Transacciones existentes en esta cuenta: {len(existing)}")
    
    for txn in existing:
        if txn.transaction_type in ('DEPOSIT', 'WITHDRAWAL', 'FEE', 'DIVIDEND'):
            key = (
                txn.transaction_type,
                txn.asset_id,
                txn.transaction_date.isoformat() if txn.transaction_date else None,
                float(txn.amount) if txn.amount else 0,
                0  # placeholder
            )
            existing_transactions_snapshot.add(key)
            
            if txn.transaction_type == 'DEPOSIT':
                print(f"   📌 Snapshot DEPOSIT: {key}")
    
    print(f"\n   Total claves en snapshot: {len(existing_transactions_snapshot)}")
    print("")
    
    # 3. Parsear CSV y verificar cada depósito
    print("="*80)
    print("2. PARSEAR CSV Y VERIFICAR DUPLICADOS")
    print("="*80)
    
    csv_file = os.path.join(os.path.dirname(__file__), 'uploads', 'U12722327_20230912_20240911.csv')
    if not os.path.exists(csv_file):
        print(f"❌ No se encontró el CSV: {csv_file}")
        sys.exit(1)
    
    parser = IBKRParser()
    parsed_data = parser.parse(csv_file)
    
    csv_deposits = parsed_data.get('deposits', [])
    print(f"   Depósitos parseados del CSV: {len(csv_deposits)}")
    print("")
    
    # 4. Simular el proceso de importación
    print("="*80)
    print("3. SIMULACIÓN DEL PROCESO DE IMPORTACIÓN")
    print("="*80)
    
    for i, deposit_data in enumerate(csv_deposits, 1):
        print(f"\n   Depósito {i}/{len(csv_deposits)}:")
        print(f"   - CSV Data: {deposit_data}")
        
        # Procesar como lo hace _import_cash_movements
        deposit_date_raw = deposit_data.get('date') or deposit_data.get('date_time')
        deposit_date = parse_datetime(deposit_date_raw)
        deposit_amount = float(deposit_data['amount'])
        
        print(f"   - Fecha parseada: {deposit_date}")
        print(f"   - Monto: {deposit_amount}")
        
        if not deposit_date:
            print(f"   ❌ PROBLEMA: Fecha inválida - se saltaría")
            continue
        
        # Crear clave como lo hace el importer
        deposit_date_str = deposit_date.isoformat()
        deposit_key = (
            'DEPOSIT',
            None,  # asset_id es None para depósitos
            deposit_date_str,
            deposit_amount,
            0  # placeholder
        )
        
        print(f"   - Clave generada: {deposit_key}")
        
        # Verificar si existe en snapshot
        if deposit_key in existing_transactions_snapshot:
            print(f"   ⏭️  DUPLICADO DETECTADO - Se saltaría")
            
            # Buscar la transacción existente
            matching_txn = Transaction.query.filter_by(
                user_id=user_id,
                account_id=account_id,
                transaction_type='DEPOSIT',
                transaction_date=deposit_date
            ).first()
            
            # Verificar si el monto coincide (con tolerancia)
            if matching_txn and abs(float(matching_txn.amount) - deposit_amount) < 0.01:
                print(f"      └─ Coincide con: ID {matching_txn.id}, Source: {matching_txn.source}, Amount: {matching_txn.amount}")
        else:
            print(f"   ✅ NO ES DUPLICADO - Se importaría")
    
    print("")
    print("="*80)
    print("4. VERIFICACIÓN ADICIONAL: Depósitos por account_id")
    print("="*80)
    
    # Verificar si hay depósitos con account_id diferente o None
    all_deposits_user = Transaction.query.filter_by(
        user_id=user_id,
        transaction_type='DEPOSIT'
    ).all()
    
    deposits_by_account = {}
    for dep in all_deposits_user:
        acc_id = dep.account_id
        if acc_id not in deposits_by_account:
            deposits_by_account[acc_id] = []
        deposits_by_account[acc_id].append(dep)
    
    print(f"   Depósitos del usuario en todas las cuentas: {len(all_deposits_user)}")
    for acc_id, deps in deposits_by_account.items():
        acc = BrokerAccount.query.get(acc_id) if acc_id else None
        acc_name = acc.account_name if acc else f"Account ID {acc_id} (None?)"
        broker_name = acc.broker.name if acc and acc.broker else "Unknown"
        print(f"   - {acc_name} ({broker_name}): {len(deps)} depósitos")
        
        # Verificar si alguno tiene account_id None o incorrecto
        for dep in deps:
            if dep.account_id != acc_id:
                print(f"      ⚠️  Depósito ID {dep.id} tiene account_id={dep.account_id} (esperado {acc_id})")
    
    print("")
    print("="*80)
    print("CONCLUSIÓN")
    print("="*80)

