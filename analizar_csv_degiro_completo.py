"""
Analizar CSV de DeGiro para identificar transacciones no contabilizadas
y verificar conversiones de moneda
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.parsers.degiro_parser import DeGiroParser
from app.services.currency_service import convert_to_eur
from collections import defaultdict
import csv

app = create_app()

with app.app_context():
    user = User.query.first()
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"ANÁLISIS COMPLETO: Transacciones del CSV vs BD")
    print(f"{'='*80}\n")
    
    # 1. Analizar el CSV directamente
    csv_path = '/home/ssoo/www/uploads/Account (1).csv'
    
    print("📄 ANALIZANDO CSV DE DEGIRO...")
    print(f"   Archivo: {csv_path}\n")
    
    # Leer CSV y agrupar por tipo de descripción
    transaction_types_csv = defaultdict(list)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            descripcion = row.get('Descripción', '').strip()
            amount_str = row.get('__amount__', '0').strip()
            
            try:
                # Convertir amount a float (puede tener formato europeo)
                amount_str = amount_str.replace('.', '').replace(',', '.')
                amount = float(amount_str) if amount_str else 0.0
            except:
                amount = 0.0
            
            if descripcion:
                transaction_types_csv[descripcion].append({
                    'amount': amount,
                    'currency': row.get('__currency__', 'EUR'),
                    'date': row.get('Fecha', ''),
                    'product': row.get('Producto', ''),
                    'isin': row.get('ISIN', ''),
                    'row': row
                })
    
    print("📊 TIPOS DE TRANSACCIONES EN EL CSV:\n")
    for desc_type, transactions in sorted(transaction_types_csv.items()):
        total_amount = sum(t['amount'] for t in transactions)
        print(f"  • {desc_type}: {len(transactions)} transacciones, Total: {total_amount:,.2f}")
    
    # 2. Verificar qué tipos estamos parseando
    print(f"\n{'='*80}")
    print("🔍 VERIFICACIÓN: ¿Qué tipos estamos parseando?")
    print(f"{'='*80}\n")
    
    parser = DeGiroParser()
    tipos_parseados = parser.TRANSACTION_TYPES.keys()
    
    print("Tipos que SÍ parseamos:")
    for tipo in sorted(tipos_parseados):
        print(f"  ✓ {tipo}")
    
    print("\nTipos en CSV que NO estamos parseando:")
    tipos_no_parseados = []
    for tipo_csv in sorted(transaction_types_csv.keys()):
        if tipo_csv not in tipos_parseados:
            # Verificar si es similar a alguno de los que parseamos
            es_similar = False
            for tipo_parseado in tipos_parseados:
                if tipo_csv.lower() in tipo_parseado.lower() or tipo_parseado.lower() in tipo_csv.lower():
                    es_similar = True
                    break
            if not es_similar:
                tipos_no_parseados.append(tipo_csv)
                total = sum(t['amount'] for t in transaction_types_csv[tipo_csv])
                print(f"  ⚠️  {tipo_csv}: {len(transaction_types_csv[tipo_csv])} transacciones, Total: {total:,.2f}")
    
    # 3. Analizar INTEREST (intereses)
    print(f"\n{'='*80}")
    print("💳 INTERESES (INTEREST)")
    print(f"{'='*80}\n")
    
    interests_csv = [t for tipo, trans in transaction_types_csv.items() 
                     if 'Interés' in tipo for t in trans]
    
    total_interests_csv = sum(convert_to_eur(t['amount'], t['currency']) for t in interests_csv)
    
    print(f"En el CSV:")
    print(f"  • Total intereses: € {total_interests_csv:,.2f}")
    print(f"  • Cantidad de transacciones: {len(interests_csv)}")
    
    interests_bd = Transaction.query.filter_by(user_id=user_id, transaction_type='INTEREST').all()
    total_interests_bd = sum(convert_to_eur(abs(i.amount), i.currency) for i in interests_bd)
    
    print(f"\nEn la BD:")
    print(f"  • Total intereses: € {total_interests_bd:,.2f}")
    print(f"  • Cantidad de transacciones: {len(interests_bd)}")
    
    if abs(total_interests_csv - total_interests_bd) > 0.01:
        print(f"\n  ⚠️  DIFERENCIA: € {abs(total_interests_csv - total_interests_bd):,.2f}")
    else:
        print(f"\n  ✓ Coinciden")
    
    # 4. Analizar conversiones de moneda (FX)
    print(f"\n{'='*80}")
    print("💱 CONVERSIONES DE MONEDA (FX)")
    print(f"{'='*80}\n")
    
    fx_in_csv = [t for tipo, trans in transaction_types_csv.items() 
                  if 'Ingreso Cambio de Divisa' in tipo for t in trans]
    fx_out_csv = [t for tipo, trans in transaction_types_csv.items() 
                   if 'Retirada Cambio de Divisa' in tipo for t in trans]
    
    total_fx_in_csv = sum(convert_to_eur(t['amount'], t['currency']) for t in fx_in_csv)
    total_fx_out_csv = sum(convert_to_eur(t['amount'], t['currency']) for t in fx_out_csv)
    
    print(f"En el CSV:")
    print(f"  • Ingreso Cambio de Divisa: € {total_fx_in_csv:,.2f} ({len(fx_in_csv)} transacciones)")
    print(f"  • Retirada Cambio de Divisa: € {total_fx_out_csv:,.2f} ({len(fx_out_csv)} transacciones)")
    print(f"  • Neto FX: € {total_fx_in_csv - total_fx_out_csv:,.2f}")
    
    print(f"\n  ⚠️  NOTA: Las conversiones FX normalmente se usan para emparejar con dividendos,")
    print(f"     no se registran como transacciones independientes en la BD")
    
    # 5. Verificar todas las transacciones en BD y sus totales
    print(f"\n{'='*80}")
    print("📊 RESUMEN: Total por tipo en BD")
    print(f"{'='*80}\n")
    
    tipos_bd = {
        'DEPOSIT': Transaction.query.filter_by(user_id=user_id, transaction_type='DEPOSIT').all(),
        'WITHDRAWAL': Transaction.query.filter_by(user_id=user_id, transaction_type='WITHDRAWAL').all(),
        'DIVIDEND': Transaction.query.filter_by(user_id=user_id, transaction_type='DIVIDEND').all(),
        'FEE': Transaction.query.filter_by(user_id=user_id, transaction_type='FEE').all(),
        'COMMISSION': Transaction.query.filter_by(user_id=user_id, transaction_type='COMMISSION').all(),
        'INTEREST': Transaction.query.filter_by(user_id=user_id, transaction_type='INTEREST').all(),
    }
    
    for tipo, transacciones in tipos_bd.items():
        total = sum(convert_to_eur(abs(t.amount), t.currency) for t in transacciones)
        print(f"  • {tipo}: € {total:,.2f} ({len(transacciones)} transacciones)")
    
    # 6. Comparar específicamente con CSV
    print(f"\n{'='*80}")
    print("🔍 COMPARACIÓN DETALLADA CSV vs BD")
    print(f"{'='*80}\n")
    
    # Dividends
    dividends_csv = [t for tipo, trans in transaction_types_csv.items() 
                     if 'Dividendo' in tipo and 'Retención' not in tipo for t in trans]
    total_dividends_csv = sum(convert_to_eur(t['amount'], t['currency']) for t in dividends_csv)
    total_dividends_bd = sum(convert_to_eur(abs(d.amount), d.currency) for d in tipos_bd['DIVIDEND'])
    
    print("Dividendos:")
    print(f"  CSV: € {total_dividends_csv:,.2f} ({len(dividends_csv)} transacciones)")
    print(f"  BD:  € {total_dividends_bd:,.2f} ({len(tipos_bd['DIVIDEND'])} transacciones)")
    if abs(total_dividends_csv - total_dividends_bd) > 0.01:
        print(f"  ⚠️  DIFERENCIA: € {abs(total_dividends_csv - total_dividends_bd):,.2f}")
    else:
        print(f"  ✓ Coinciden")
    
    # Deposits
    deposits_csv = [t for tipo, trans in transaction_types_csv.items() 
                    if tipo == 'Ingreso' and 'Cambio de Divisa' not in str(trans[0].get('row', {})) for t in trans]
    total_deposits_csv = sum(convert_to_eur(t['amount'], t['currency']) for t in deposits_csv)
    total_deposits_bd = sum(convert_to_eur(abs(d.amount), d.currency) for d in tipos_bd['DEPOSIT'])
    
    print(f"\nDepósitos:")
    print(f"  CSV: € {total_deposits_csv:,.2f} ({len(deposits_csv)} transacciones)")
    print(f"  BD:  € {total_deposits_bd:,.2f} ({len(tipos_bd['DEPOSIT'])} transacciones)")
    if abs(total_deposits_csv - total_deposits_bd) > 0.01:
        print(f"  ⚠️  DIFERENCIA: € {abs(total_deposits_csv - total_deposits_bd):,.2f}")
    else:
        print(f"  ✓ Coinciden")
    
    # Withdrawals
    withdrawals_csv = [t for tipo, trans in transaction_types_csv.items() 
                       if 'flatex Withdrawal' in tipo for t in trans]
    total_withdrawals_csv = sum(convert_to_eur(abs(t['amount']), t['currency']) for t in withdrawals_csv)
    total_withdrawals_bd = sum(convert_to_eur(abs(w.amount), w.currency) for w in tipos_bd['WITHDRAWAL'])
    
    print(f"\nRetiradas:")
    print(f"  CSV: € {total_withdrawals_csv:,.2f} ({len(withdrawals_csv)} transacciones)")
    print(f"  BD:  € {total_withdrawals_bd:,.2f} ({len(tipos_bd['WITHDRAWAL'])} transacciones)")
    if abs(total_withdrawals_csv - total_withdrawals_bd) > 0.01:
        print(f"  ⚠️  DIFERENCIA: € {abs(total_withdrawals_csv - total_withdrawals_bd):,.2f}")
    else:
        print(f"  ✓ Coinciden")
    
    # Fees/Commissions
    fees_csv = [t for tipo, trans in transaction_types_csv.items() 
                if 'Costes de transacción' in tipo or 'Comisión' in tipo 
                for t in trans]
    total_fees_csv = sum(convert_to_eur(abs(t['amount']), t['currency']) for t in fees_csv)
    total_fees_bd = sum(convert_to_eur(abs(f.amount), f.currency) for f in tipos_bd['FEE']) + \
                   sum(convert_to_eur(abs(c.amount), c.currency) for c in tipos_bd['COMMISSION'])
    
    print(f"\nComisiones/Fees:")
    print(f"  CSV: € {total_fees_csv:,.2f} ({len(fees_csv)} transacciones)")
    print(f"  BD:  € {total_fees_bd:,.2f} ({len(tipos_bd['FEE']) + len(tipos_bd['COMMISSION'])} transacciones)")
    if abs(total_fees_csv - total_fees_bd) > 0.01:
        print(f"  ⚠️  DIFERENCIA: € {abs(total_fees_csv - total_fees_bd):,.2f}")
    else:
        print(f"  ✓ Coinciden")
    
    print("\n" + "="*80 + "\n")

