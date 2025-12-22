#!/usr/bin/env python3
"""
Script para analizar depósitos de IBKR y comparar entre CSV y base de datos
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.broker import Broker, BrokerAccount
from app.services.parsers.ibkr_parser import IBKRParser
from app.services.currency_service import convert_to_eur
from collections import defaultdict

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
    
    print(f"📊 Analizando {len(broker_accounts)} cuenta(s) IBKR\n")
    
    for account in broker_accounts:
        user_id = account.user_id
        account_id = account.id
        
        print(f"{'='*80}")
        print(f"Cuenta: {account.account_name} (ID: {account_id}, User: {user_id})")
        print(f"{'='*80}\n")
        
        # 2. Obtener depósitos desde la base de datos
        db_deposits = Transaction.query.filter_by(
            user_id=user_id,
            account_id=account_id,
            transaction_type='DEPOSIT'
        ).order_by(Transaction.transaction_date).all()
        
        print(f"📥 Depósitos en Base de Datos: {len(db_deposits)}")
        
        total_db_eur = 0.0
        deposits_by_date = defaultdict(float)
        
        for dep in db_deposits:
            amount_eur = convert_to_eur(dep.amount, dep.currency)
            total_db_eur += amount_eur
            deposits_by_date[dep.transaction_date.date()] += amount_eur
            print(f"   - {dep.transaction_date.date()} | {dep.amount:>12,.2f} {dep.currency:3} ({amount_eur:>12,.2f} EUR) | {dep.description}")
        
        print(f"\n   Total en Base de Datos: {total_db_eur:>12,.2f} EUR\n")
        
        # 3. Buscar archivos CSV de IBKR en uploads
        uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
        if not os.path.exists(uploads_dir):
            print(f"⚠️  Directorio uploads no encontrado: {uploads_dir}")
            continue
        
        print(f"🔍 Buscando CSVs de IBKR en: {uploads_dir}\n")
        
        import glob
        csv_files = glob.glob(os.path.join(uploads_dir, '*.csv'))
        
        ibkr_csvs = []
        for csv_file in csv_files:
            try:
                # Intentar detectar si es IBKR leyendo las primeras líneas
                with open(csv_file, 'r', encoding='utf-8') as f:
                    first_lines = [f.readline() for _ in range(5)]
                    if any('Statement,' in line or 'BrokerName' in line for line in first_lines):
                        ibkr_csvs.append(csv_file)
            except Exception as e:
                continue
        
        if not ibkr_csvs:
            print("⚠️  No se encontraron CSVs de IBKR")
            continue
        
        # 4. Analizar cada CSV de IBKR
        for csv_file in sorted(ibkr_csvs, key=os.path.getmtime, reverse=True)[:5]:  # Últimos 5
            print(f"\n{'─'*80}")
            print(f"📄 Analizando CSV: {os.path.basename(csv_file)}")
            print(f"{'─'*80}\n")
            
            try:
                parser = IBKRParser()
                parsed_data = parser.parse(csv_file)
                
                # Mostrar secciones detectadas
                print(f"📋 Secciones detectadas en el CSV:")
                for section_name in sorted(parser.sections.keys()):
                    data_count = len(parser.sections[section_name].get('data', []))
                    print(f"   - {section_name}: {data_count} filas de datos")
                
                # Verificar si se encontró la sección de depósitos
                deposits_section = parser.sections.get('Depósitos y retiradas') or \
                                  parser.sections.get('Deposits & Withdrawals')
                
                if not deposits_section:
                    print(f"\n⚠️  ADVERTENCIA: No se encontró la sección 'Depósitos y retiradas' o 'Deposits & Withdrawals'")
                    print(f"   Secciones disponibles relacionadas con depósitos:")
                    for section_name in parser.sections.keys():
                        if 'deposit' in section_name.lower() or 'retira' in section_name.lower() or 'withdraw' in section_name.lower():
                            print(f"   - {section_name}")
                else:
                    print(f"\n✅ Sección de depósitos encontrada: {deposits_section}")
                    print(f"   Filas de datos: {len(deposits_section.get('data', []))}")
                
                # Mostrar depósitos parseados
                csv_deposits = parsed_data.get('deposits', [])
                print(f"\n💰 Depósitos parseados del CSV: {len(csv_deposits)}")
                
                total_csv_eur = 0.0
                csv_deposits_by_date = defaultdict(float)
                
                for dep in csv_deposits:
                    amount_eur = convert_to_eur(dep['amount'], dep['currency'])
                    total_csv_eur += amount_eur
                    csv_deposits_by_date[dep['date'].date()] += amount_eur
                    print(f"   - {dep['date'].date()} | {dep['amount']:>12,.2f} {dep['currency']:3} ({amount_eur:>12,.2f} EUR) | {dep.get('description', 'N/A')}")
                
                print(f"\n   Total en CSV: {total_csv_eur:>12,.2f} EUR")
                
                # Comparar
                difference = total_csv_eur - total_db_eur
                print(f"\n📊 Comparación:")
                print(f"   CSV Total:  {total_csv_eur:>12,.2f} EUR")
                print(f"   DB Total:   {total_db_eur:>12,.2f} EUR")
                print(f"   Diferencia: {difference:>12,.2f} EUR")
                
                if abs(difference) > 0.01:
                    print(f"\n⚠️  HAY DIFERENCIA entre CSV y Base de Datos")
                    
                    # Buscar depósitos en CSV que no están en DB
                    print(f"\n🔍 Depósitos en CSV que NO están en DB (por fecha y monto):")
                for dep in csv_deposits:
                    # Manejar fecha (puede ser datetime o string)
                    dep_date_obj = dep['date']
                    if isinstance(dep_date_obj, str):
                        from datetime import datetime
                        dep_date_obj = datetime.strptime(dep_date_obj, '%Y-%m-%d')
                    dep_date = dep_date_obj.date() if hasattr(dep_date_obj, 'date') else dep_date_obj
                    
                    dep_amount_eur = convert_to_eur(dep['amount'], dep['currency'])
                    
                    # Buscar en DB si existe uno igual (misma fecha y monto similar)
                    found = False
                    for db_dep in db_deposits:
                        if db_dep.transaction_date.date() == dep_date:
                                db_amount_eur = convert_to_eur(db_dep.amount, db_dep.currency)
                                if abs(db_amount_eur - dep_amount_eur) < 0.01:
                                    found = True
                                    break
                        
                        if not found:
                            print(f"   - {dep_date} | {dep['amount']:>12,.2f} {dep['currency']:3} ({dep_amount_eur:>12,.2f} EUR) | {dep.get('description', 'N/A')}")
                
            except Exception as e:
                print(f"❌ Error procesando CSV: {e}")
                import traceback
                traceback.print_exc()
                continue

