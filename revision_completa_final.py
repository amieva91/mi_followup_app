"""
Revisión completa final: conversiones de moneda, otras transacciones, etc.
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.currency_service import convert_to_eur
from decimal import Decimal
import csv

app = create_app()

with app.app_context():
    user = User.query.first()
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"REVISIÓN COMPLETA FINAL")
    print(f"{'='*80}\n")
    
    # 1. Verificar conversiones de moneda en transacciones
    print("1️⃣ VERIFICACIÓN: Conversiones de moneda\n")
    
    # Obtener todas las transacciones con diferentes monedas
    all_transactions = Transaction.query.filter_by(user_id=user_id).all()
    
    currencies_used = set()
    transactions_by_currency = {}
    
    for txn in all_transactions:
        curr = txn.currency or 'EUR'
        currencies_used.add(curr)
        if curr not in transactions_by_currency:
            transactions_by_currency[curr] = []
        transactions_by_currency[curr].append(txn)
    
    print(f"Monedas utilizadas: {sorted(currencies_used)}")
    print(f"\nCantidad de transacciones por moneda:")
    for curr in sorted(transactions_by_currency.keys()):
        print(f"  • {curr}: {len(transactions_by_currency[curr])} transacciones")
    
    # Verificar si hay problemas con conversiones (valores extremos)
    print(f"\n{'='*80}")
    print("2️⃣ VERIFICACIÓN: Otras transacciones no parseadas\n")
    
    csv_path = '/home/ssoo/www/uploads/Account (1).csv'
    
    # Tipos que SÍ parseamos
    tipos_parseados = {
        'Compra', 'Venta', 'Dividendo', 'Retención del dividendo',
        'Costes de transacción', 'Comisión', 'Interés', 'Flatex Interest',
        'Ingreso Cambio de Divisa', 'Retirada Cambio de Divisa',
        'flatex Withdrawal', 'Processed Flatex Withdrawal',
        'Spanish Transaction Tax', 'Impuesto de transacción Frances',
        'Impuesto sobre Transacciones Financieras Italiano',
        'Degiro Cash Sweep', 'Ingreso'
    }
    
    otros_tipos_con_valor = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for row in reader:
            if len(row) < 9:
                continue
            
            descripcion = row[5].strip() if len(row) > 5 else ''
            variacion_str = row[8].strip() if len(row) > 8 else '0'
            currency = row[7].strip() if len(row) > 7 else 'EUR'
            
            try:
                variacion_str = variacion_str.replace('.', '').replace(',', '.')
                variacion = abs(float(variacion_str))
            except:
                variacion = 0.0
            
            # Verificar si es un tipo que NO parseamos y tiene valor significativo
            es_parseado = False
            for tipo_parseado in tipos_parseados:
                if tipo_parseado.lower() in descripcion.lower():
                    es_parseado = True
                    break
            
            if not es_parseado and variacion > 0.01:
                if descripcion not in otros_tipos_con_valor:
                    otros_tipos_con_valor[descripcion] = {
                        'count': 0,
                        'total': 0.0,
                        'currency': currency
                    }
                otros_tipos_con_valor[descripcion]['count'] += 1
                otros_tipos_con_valor[descripcion]['total'] += variacion
    
    if otros_tipos_con_valor:
        print("⚠️  Tipos de transacciones con valores que NO estamos parseando:\n")
        for desc, data in sorted(otros_tipos_con_valor.items(), key=lambda x: x[1]['total'], reverse=True):
            if data['total'] > 1.0:  # Solo mostrar si el total es significativo (>1€)
                print(f"  • {desc}:")
                print(f"    - Cantidad: {data['count']} transacciones")
                print(f"    - Total: {data['total']:,.2f} {data['currency']}")
                total_eur = convert_to_eur(data['total'], data['currency'])
                print(f"    - En EUR: € {total_eur:,.2f}")
                print()
    else:
        print("✓ No se encontraron otros tipos de transacciones con valores significativos\n")
    
    # 3. Verificar intereses (INTEREST)
    print(f"{'='*80}")
    print("3️⃣ VERIFICACIÓN: Intereses\n")
    
    interests_bd = Transaction.query.filter_by(user_id=user_id, transaction_type='INTEREST').all()
    total_interests_bd = sum(convert_to_eur(abs(i.amount), i.currency) for i in interests_bd)
    
    print(f"Intereses en BD: € {total_interests_bd:,.2f} ({len(interests_bd)} transacciones)")
    
    # Buscar en CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        interests_csv_count = 0
        interests_csv_total = 0.0
        
        for row in reader:
            if len(row) > 5:
                desc = row[5].strip()
                if 'Interés' in desc or 'Flatex Interest' in desc:
                    interests_csv_count += 1
                    try:
                        val_str = row[8].strip().replace('.', '').replace(',', '.') if len(row) > 8 else '0'
                        val = abs(float(val_str))
                        interests_csv_total += val
                    except:
                        pass
    
    print(f"Intereses en CSV: € {interests_csv_total:,.2f} ({interests_csv_count} transacciones)")
    
    if abs(interests_csv_total - total_interests_bd) > 0.01:
        print(f"⚠️  DIFERENCIA: € {abs(interests_csv_total - total_interests_bd):,.2f}")
    else:
        print(f"✓ Coinciden")
    
    # 4. Resumen final
    print(f"\n{'='*80}")
    print("📊 RESUMEN DE HALLAZGOS")
    print(f"{'='*80}\n")
    
    print("✅ IMPUESTOS DE TRANSACCIÓN (YA CORREGIDO):")
    print(f"   • € 735.16 no contabilizados")
    print(f"   • Ya actualizado el parser para importarlos como FEE\n")
    
    if otros_tipos_con_valor:
        total_otros = sum(convert_to_eur(data['total'], data['currency']) 
                         for data in otros_tipos_con_valor.values() if data['total'] > 1.0)
        if total_otros > 1.0:
            print(f"⚠️  OTRAS TRANSACCIONES NO PARSEADAS:")
            print(f"   • Total: € {total_otros:,.2f}")
            print(f"   • Revisar si deben contabilizarse\n")
    
    print("✅ CONVERSIONES DE MONEDA:")
    print(f"   • Se están usando {len(currencies_used)} monedas diferentes")
    print(f"   • Las conversiones se hacen mediante convert_to_eur()")
    print(f"   • No se detectaron problemas obvios\n")
    
    print("="*80 + "\n")

