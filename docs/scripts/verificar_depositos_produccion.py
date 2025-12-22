#!/usr/bin/env python3
"""
Script para verificar si los depósitos de IBKR ya existen en producción
y entender por qué se están saltando durante la importación
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
    
    print(f"📊 Analizando cuenta IBKR: {account.account_name} (ID: {account_id})\n")
    
    # 2. Parsear el CSV completo
    csv_file = os.path.join(os.path.dirname(__file__), 'uploads', 'U12722327_20230912_20240911.csv')
    if not os.path.exists(csv_file):
        print(f"❌ No se encontró el CSV: {csv_file}")
        sys.exit(1)
    
    print(f"📄 Parseando CSV: {os.path.basename(csv_file)}\n")
    parser = IBKRParser()
    parsed_data = parser.parse(csv_file)
    
    csv_deposits = parsed_data.get('deposits', [])
    print(f"💰 Depósitos encontrados en CSV: {len(csv_deposits)}\n")
    
    # 3. Obtener depósitos existentes en DB
    db_deposits = Transaction.query.filter_by(
        user_id=user_id,
        account_id=account_id,
        transaction_type='DEPOSIT'
    ).order_by(Transaction.transaction_date).all()
    
    print(f"📥 Depósitos existentes en Base de Datos: {len(db_deposits)}\n")
    
    # 4. Crear snapshot como lo hace el importer (para comparación exacta)
    print(f"{'='*80}")
    print(f"🔍 Verificando coincidencias EXACTAS (usando la misma lógica del importer):")
    print(f"{'='*80}\n")
    
    # Crear snapshot como en _create_transaction_snapshot
    existing_snapshot = set()
    for txn in db_deposits:
        key = (
            txn.transaction_type,
            txn.asset_id,
            txn.transaction_date.isoformat() if txn.transaction_date else None,
            float(txn.amount) if txn.amount else 0,
            0  # placeholder
        )
        existing_snapshot.add(key)
        print(f"   📌 Snapshot DB: {key}")
    
    print(f"\n   Total en snapshot: {len(existing_snapshot)} claves\n")
    
    # 5. Verificar cada depósito del CSV contra el snapshot
    print(f"{'='*80}")
    print(f"🔍 Verificando depósitos del CSV contra snapshot:")
    print(f"{'='*80}\n")
    
    matches = 0
    non_matches = 0
    
    for csv_dep in csv_deposits:
        # Convertir fecha como lo hace el importer
        from app.services.importer_v2 import parse_datetime
        deposit_date_raw = csv_dep.get('date') or csv_dep.get('date_time')
        deposit_date = parse_datetime(deposit_date_raw)
        
        if not deposit_date:
            print(f"   ⚠️  Depósito sin fecha válida: {csv_dep}")
            continue
        
        deposit_amount = float(csv_dep['amount'])
        deposit_date_str = deposit_date.isoformat()
        
        # Crear clave como en _import_cash_movements
        deposit_key = (
            'DEPOSIT',
            None,  # asset_id es None para depósitos
            deposit_date_str,
            deposit_amount,
            0  # placeholder
        )
        
        # Verificar si existe en snapshot
        date_display = deposit_date.date()
        if deposit_key in existing_snapshot:
            matches += 1
            print(f"   ✅ {date_display} | {deposit_amount:>12,.2f} EUR | COINCIDE (sería saltado como duplicado)")
            
            # Buscar el depósito exacto en DB para mostrar detalles
            for db_dep in db_deposits:
                if (db_dep.transaction_date.date() == date_display and 
                    abs(float(db_dep.amount) - deposit_amount) < 0.01):
                    print(f"      └─ DB ID: {db_dep.id}, Source: {db_dep.source}, Desc: {db_dep.description}")
                    break
        else:
            non_matches += 1
            print(f"   ❌ {date_display} | {deposit_amount:>12,.2f} EUR | NO COINCIDE (debería importarse)")
            print(f"      └─ Clave buscada: {deposit_key}")
            
            # Buscar depósitos similares en DB (misma fecha pero diferente monto)
            similar = [d for d in db_deposits if d.transaction_date.date() == date_display]
            if similar:
                print(f"      └─ Depósitos en DB con misma fecha:")
                for s in similar:
                    print(f"         • ID {s.id}: {s.amount:>12,.2f} EUR (diff: {abs(float(s.amount) - deposit_amount):.2f})")
    
    print(f"\n{'='*80}")
    print(f"📊 Resumen:")
    print(f"{'='*80}")
    print(f"   Depósitos en CSV: {len(csv_deposits)}")
    print(f"   Depósitos en DB: {len(db_deposits)}")
    print(f"   Coincidencias exactas: {matches} (serían saltados)")
    print(f"   No coincidencias: {non_matches} (deberían importarse)")
    
    if matches == len(csv_deposits):
        print(f"\n   ✅ CONCLUSIÓN: Todos los depósitos del CSV ya existen en la DB")
        print(f"      Por eso se saltan durante la importación (detección de duplicados funcionando correctamente)")
    elif non_matches > 0:
        print(f"\n   ⚠️  CONCLUSIÓN: Hay {non_matches} depósito(s) que NO existen en DB pero no se importaron")
        print(f"      Esto indica un problema en el proceso de importación")
    else:
        print(f"\n   ❓ CONCLUSIÓN: Situación inesperada - revisar logs de importación")

