"""
Analizar CSV de DeGiro correctamente para identificar transacciones no contabilizadas
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.currency_service import convert_to_eur
from collections import defaultdict
import csv

app = create_app()

with app.app_context():
    user = User.query.first()
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"ANÁLISIS MEJORADO: Transacciones del CSV vs BD")
    print(f"{'='*80}\n")
    
    # Leer CSV correctamente
    csv_path = '/home/ssoo/www/uploads/Account (1).csv'
    
    transaction_types_csv = defaultdict(lambda: {'count': 0, 'total_eur': 0.0, 'transactions': []})
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Saltar header
        
        for row in reader:
            if len(row) < 9:
                continue
            
            descripcion = row[5] if len(row) > 5 else ''  # Columna Descripción
            variacion_str = row[7] if len(row) > 7 else '0'  # Columna Variación (sin nombre)
            currency = row[8] if len(row) > 8 else 'EUR'  # Columna Moneda (sin nombre)
            
            try:
                # Limpiar y convertir variacion (formato europeo: -10,04)
                variacion_str = variacion_str.strip().replace('.', '').replace(',', '.')
                variacion = float(variacion_str) if variacion_str else 0.0
            except:
                variacion = 0.0
            
            if descripcion and descripcion.strip():
                desc_clean = descripcion.strip()
                variacion_eur = convert_to_eur(variacion, currency)
                
                transaction_types_csv[desc_clean]['count'] += 1
                transaction_types_csv[desc_clean]['total_eur'] += variacion_eur
                transaction_types_csv[desc_clean]['transactions'].append({
                    'amount': variacion,
                    'currency': currency,
                    'amount_eur': variacion_eur
                })
    
    print("📊 TODOS LOS TIPOS DE TRANSACCIONES EN EL CSV:\n")
    
    # Agrupar por categorías
    compras_ventas = []
    dividendos = []
    comisiones_fees = []
    impuestos = []
    depositos_retiradas = []
    fx = []
    otros = []
    
    for desc_type, data in sorted(transaction_types_csv.items()):
        total = data['total_eur']
        count = data['count']
        
        if 'Compra' in desc_type or 'Venta' in desc_type:
            compras_ventas.append((desc_type, total, count))
        elif 'Dividendo' in desc_type and 'Retención' not in desc_type:
            dividendos.append((desc_type, total, count))
        elif 'Costes de transacción' in desc_type or 'Comisión' in desc_type:
            comisiones_fees.append((desc_type, total, count))
        elif 'Impuesto' in desc_type or 'Tax' in desc_type or 'Retención' in desc_type:
            impuestos.append((desc_type, total, count))
        elif 'Ingreso' in desc_type and 'Cambio de Divisa' not in desc_type:
            depositos_retiradas.append((desc_type, total, count))
        elif 'flatex Withdrawal' in desc_type or 'Transferir' in desc_type:
            depositos_retiradas.append((desc_type, total, count))
        elif 'Cambio de Divisa' in desc_type:
            fx.append((desc_type, total, count))
        else:
            otros.append((desc_type, total, count))
    
    print("💰 DEPÓSITOS/RETIRADAS:")
    total_depositos = 0.0
    total_retiradas = 0.0
    for desc, total, count in depositos_retiradas:
        print(f"  • {desc}: € {total:,.2f} ({count} transacciones)")
        if 'Ingreso' in desc or 'Deposit' in desc:
            total_depositos += total
        elif 'Withdrawal' in desc or 'Retirada' in desc or 'Transferir desde' in desc:
            total_retiradas += total
    
    print(f"\n  Total Depósitos CSV: € {total_depositos:,.2f}")
    print(f"  Total Retiradas CSV: € {total_retiradas:,.2f}")
    
    print("\n📈 DIVIDENDOS:")
    total_dividendos_csv = 0.0
    for desc, total, count in dividendos:
        print(f"  • {desc}: € {total:,.2f} ({count} transacciones)")
        total_dividendos_csv += total
    print(f"\n  Total Dividendos CSV: € {total_dividendos_csv:,.2f}")
    
    print("\n💳 COMISIONES/FEES:")
    total_comisiones_csv = 0.0
    for desc, total, count in comisiones_fees:
        print(f"  • {desc}: € {total:,.2f} ({count} transacciones)")
        total_comisiones_csv += total
    print(f"\n  Total Comisiones/Fees CSV: € {total_comisiones_csv:,.2f}")
    
    print("\n📋 IMPUESTOS:")
    total_impuestos_csv = 0.0
    for desc, total, count in impuestos:
        print(f"  • {desc}: € {total:,.2f} ({count} transacciones)")
        total_impuestos_csv += total
    print(f"\n  ⚠️  Total Impuestos CSV: € {total_impuestos_csv:,.2f}")
    print(f"  ⚠️  ESTOS IMPUESTOS NO ESTAMOS CONTABILIZÁNDOLOS COMO FEE!")
    
    print("\n💱 CONVERSIONES FX (para referencia):")
    total_fx_in = 0.0
    total_fx_out = 0.0
    for desc, total, count in fx:
        print(f"  • {desc}: € {total:,.2f} ({count} transacciones)")
        if 'Ingreso' in desc:
            total_fx_in += total
        else:
            total_fx_out += total
    print(f"\n  Neto FX: € {total_fx_in - total_fx_out:,.2f} (estas no se cuentan como transacciones)")
    
    if otros:
        print("\n❓ OTROS TIPOS (revisar si necesitan contabilizarse):")
        for desc, total, count in otros[:20]:  # Mostrar solo los primeros 20
            print(f"  • {desc}: € {total:,.2f} ({count} transacciones)")
        if len(otros) > 20:
            print(f"  ... y {len(otros) - 20} tipos más")
    
    # Comparar con BD
    print(f"\n{'='*80}")
    print("🔍 COMPARACIÓN CON BASE DE DATOS")
    print(f"{'='*80}\n")
    
    deposits_bd = Transaction.query.filter_by(user_id=user_id, transaction_type='DEPOSIT').all()
    withdrawals_bd = Transaction.query.filter_by(user_id=user_id, transaction_type='WITHDRAWAL').all()
    dividends_bd = Transaction.query.filter_by(user_id=user_id, transaction_type='DIVIDEND').all()
    fees_bd = Transaction.query.filter_by(user_id=user_id).filter(
        Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
    ).all()
    
    total_deposits_bd = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits_bd)
    total_withdrawals_bd = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals_bd)
    total_dividends_bd = sum(convert_to_eur(abs(d.amount), d.currency) for d in dividends_bd)
    total_fees_bd = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees_bd)
    
    print("Depósitos:")
    print(f"  CSV: € {total_depositos:,.2f}")
    print(f"  BD:  € {total_deposits_bd:,.2f}")
    print(f"  Diferencia: € {abs(total_depositos - total_deposits_bd):,.2f}")
    
    print(f"\nRetiradas:")
    print(f"  CSV: € {total_retiradas:,.2f}")
    print(f"  BD:  € {total_withdrawals_bd:,.2f}")
    print(f"  Diferencia: € {abs(total_retiradas - total_withdrawals_bd):,.2f}")
    
    print(f"\nDividendos:")
    print(f"  CSV: € {total_dividendos_csv:,.2f}")
    print(f"  BD:  € {total_dividends_bd:,.2f}")
    print(f"  Diferencia: € {abs(total_dividendos_csv - total_dividends_bd):,.2f}")
    
    print(f"\nComisiones/Fees (sin impuestos):")
    print(f"  CSV: € {total_comisiones_csv:,.2f}")
    print(f"  BD:  € {total_fees_bd:,.2f}")
    print(f"  Diferencia: € {abs(total_comisiones_csv - total_fees_bd):,.2f}")
    
    print(f"\n{'='*80}")
    print("⚠️  IMPUESTOS NO CONTABILIZADOS")
    print(f"{'='*80}\n")
    
    print(f"Los impuestos (€ {total_impuestos_csv:,.2f}) NO están siendo contabilizados como FEE")
    print(f"Esto podría explicar parte de la diferencia en el Total B/P")
    
    print(f"\nSi añadimos los impuestos a las comisiones:")
    print(f"  Comisiones + Impuestos: € {total_comisiones_csv + total_impuestos_csv:,.2f}")
    print(f"  Comisiones en BD: € {total_fees_bd:,.2f}")
    print(f"  Diferencia: € {abs((total_comisiones_csv + total_impuestos_csv) - total_fees_bd):,.2f}")
    
    # Verificar si los impuestos están en alguna transacción de BD
    print(f"\n🔍 Buscando impuestos en transacciones de BD...")
    taxes_in_bd = Transaction.query.filter_by(user_id=user_id).filter(
        Transaction.description.like('%Impuesto%') |
        Transaction.description.like('%Tax%') |
        Transaction.description.like('%Retención%')
    ).all()
    
    if taxes_in_bd:
        total_taxes_bd = sum(convert_to_eur(abs(t.amount), t.currency) for t in taxes_in_bd)
        print(f"  Se encontraron {len(taxes_in_bd)} transacciones con impuestos en BD")
        print(f"  Total: € {total_taxes_bd:,.2f}")
        print(f"  Tipo: {set(t.transaction_type for t in taxes_in_bd)}")
    else:
        print(f"  ⚠️  NO se encontraron impuestos en BD")
        print(f"  Los impuestos del CSV NO se están importando")
    
    print("\n" + "="*80 + "\n")

