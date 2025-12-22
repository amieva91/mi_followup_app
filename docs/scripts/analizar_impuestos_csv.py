"""
Analizar impuestos y otras transacciones no contabilizadas usando el parser de DeGiro
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.parsers.degiro_parser import DeGiroParser
from app.services.currency_service import convert_to_eur

app = create_app()

with app.app_context():
    user = User.query.first()
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"ANÁLISIS: Impuestos y transacciones no contabilizadas")
    print(f"{'='*80}\n")
    
    # Usar el parser para analizar el CSV
    csv_path = '/home/ssoo/www/uploads/Account (1).csv'
    parser = DeGiroParser()
    
    # Leer el CSV manualmente para analizar todas las transacciones
    import csv
    
    impuestos = []
    other_transactions = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for row in reader:
            if len(row) < 9:
                continue
            
            descripcion = row[5].strip() if len(row) > 5 else ''
            variacion_str = row[7].strip() if len(row) > 7 else '0'
            currency = row[8].strip() if len(row) > 8 else 'EUR'
            
            try:
                # Formato: "-10,04" o "10,04"
                variacion_str = variacion_str.replace('.', '').replace(',', '.')
                variacion = float(variacion_str)
            except:
                variacion = 0.0
            
            # Buscar impuestos
            if 'Impuesto' in descripcion or 'Tax' in descripcion or 'Spanish Transaction Tax' in descripcion:
                impuestos.append({
                    'desc': descripcion,
                    'amount': variacion,
                    'currency': currency,
                    'amount_eur': convert_to_eur(variacion, currency),
                    'date': row[0] if len(row) > 0 else ''
                })
            
            # Buscar otras transacciones que no estemos parseando
            if descripcion and descripcion not in parser.TRANSACTION_TYPES:
                # Verificar si es similar a alguno conocido
                es_conocido = False
                for tipo_conocido in parser.TRANSACTION_TYPES.keys():
                    if tipo_conocido.lower() in descripcion.lower() or descripcion.lower() in tipo_conocido.lower():
                        es_conocido = True
                        break
                
                if not es_conocido and variacion != 0:
                    other_transactions.append({
                        'desc': descripcion,
                        'amount': variacion,
                        'currency': currency,
                        'amount_eur': convert_to_eur(variacion, currency),
                        'date': row[0] if len(row) > 0 else ''
                    })
    
    print("📋 IMPUESTOS ENCONTRADOS EN EL CSV:\n")
    
    total_impuestos = 0.0
    impuestos_por_tipo = {}
    
    for imp in impuestos:
        tipo = imp['desc']
        if tipo not in impuestos_por_tipo:
            impuestos_por_tipo[tipo] = {'count': 0, 'total_eur': 0.0}
        impuestos_por_tipo[tipo]['count'] += 1
        impuestos_por_tipo[tipo]['total_eur'] += imp['amount_eur']
        total_impuestos += imp['amount_eur']
    
    for tipo, data in sorted(impuestos_por_tipo.items()):
        print(f"  • {tipo}:")
        print(f"    - Cantidad: {data['count']} transacciones")
        print(f"    - Total: € {data['total_eur']:,.2f}")
    
    print(f"\n  TOTAL IMPUESTOS: € {total_impuestos:,.2f}")
    
    # Verificar si están en BD
    print(f"\n🔍 Verificando si los impuestos están en la BD...")
    
    # Buscar por descripción
    taxes_in_bd = Transaction.query.filter_by(user_id=user_id).filter(
        db.or_(
            Transaction.description.like('%Impuesto%'),
            Transaction.description.like('%Tax%'),
            Transaction.description.like('%Spanish Transaction%'),
            Transaction.transaction_type == 'TAX'
        )
    ).all()
    
    if taxes_in_bd:
        total_taxes_bd = sum(convert_to_eur(abs(t.amount), t.currency) for t in taxes_in_bd)
        print(f"  ✓ Se encontraron {len(taxes_in_bd)} transacciones de impuestos en BD")
        print(f"    Total: € {total_taxes_bd:,.2f}")
        print(f"    Tipos: {set(t.transaction_type for t in taxes_in_bd)}")
    else:
        print(f"  ⚠️  NO se encontraron impuestos en BD")
        print(f"  ⚠️  Los impuestos del CSV (€ {total_impuestos:,.2f}) NO se están importando")
    
    # Verificar cómo se manejan los impuestos en el parser
    print(f"\n{'='*80}")
    print("🔍 ¿CÓMO SE MANEJAN LOS IMPUESTOS EN EL PARSER?")
    print(f"{'='*80}\n")
    
    print("En el parser DeGiroParser:")
    print("  • 'Retención del dividendo' -> 'TAX'")
    print("  • Pero 'Impuesto de transacción Frances', 'Spanish Transaction Tax', etc.")
    print("    NO están mapeados en TRANSACTION_TYPES")
    
    print(f"\n⚠️  CONCLUSIÓN:")
    print(f"  Los impuestos de transacción (€ {total_impuestos:,.2f}) NO se están importando")
    print(f"  Solo se importan las 'Retención del dividendo' como TAX")
    
    print(f"\n💡 IMPACTO:")
    print(f"  Si estos impuestos deberían contarse como FEE, estamos subestimando los gastos")
    print(f"  en € {total_impuestos:,.2f}")
    print(f"  Esto podría explicar parte de la diferencia en el Total B/P con DeGiro")
    
    # Mostrar algunas otras transacciones que no estamos parseando
    if other_transactions:
        print(f"\n{'='*80}")
        print("❓ OTRAS TRANSACCIONES NO PARSEADAS (primeras 10):")
        print(f"{'='*80}\n")
        
        for i, other in enumerate(other_transactions[:10], 1):
            print(f"  {i}. {other['desc']}")
            print(f"     Monto: {other['amount']} {other['currency']} (€ {other['amount_eur']:,.2f})")
            print(f"     Fecha: {other['date']}")
            print()
    
    print("="*80 + "\n")

