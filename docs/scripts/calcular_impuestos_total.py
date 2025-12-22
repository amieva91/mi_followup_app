"""
Calcular correctamente el total de impuestos del CSV
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction

app = create_app()

with app.app_context():
    import csv
    
    csv_path = '/home/ssoo/www/uploads/Account (1).csv'
    
    impuestos_totales = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for row in reader:
            if len(row) < 9:
                continue
            
            descripcion = row[5].strip() if len(row) > 5 else ''
            variacion_str = row[7] if len(row) > 7 else '0'  # Ya viene sin comillas del csv.reader
            currency = row[8].strip() if len(row) > 8 else 'EUR'
            
            # Los valores vienen como "-10,04" (formato europeo)
            if 'Impuesto' in descripcion or 'Spanish Transaction Tax' in descripcion or 'Tax' in descripcion:
                try:
                    # Convertir formato europeo a float
                    variacion_str = variacion_str.strip().replace('.', '').replace(',', '.')
                    variacion = float(variacion_str)
                    
                    # Para impuestos, el valor es negativo (es un gasto)
                    if variacion > 0:
                        variacion = -variacion
                    
                    tipo = descripcion
                    if tipo not in impuestos_totales:
                        impuestos_totales[tipo] = {
                            'count': 0,
                            'total': 0.0,
                            'currency': currency
                        }
                    
                    impuestos_totales[tipo]['count'] += 1
                    impuestos_totales[tipo]['total'] += abs(variacion)  # Guardar valor absoluto
                    
                except Exception as e:
                    print(f"Error procesando: {descripcion}, valor: {variacion_str}, error: {e}")
                    continue
    
    print(f"\n{'='*80}")
    print(f"TOTAL DE IMPUESTOS EN EL CSV")
    print(f"{'='*80}\n")
    
    total_general = 0.0
    
    for tipo, data in sorted(impuestos_totales.items()):
        total_tipo = data['total']
        total_general += total_tipo
        print(f"  • {tipo}:")
        print(f"    - Cantidad: {data['count']} transacciones")
        print(f"    - Total: € {total_tipo:,.2f}")
        print()
    
    print(f"  {'='*60}")
    print(f"  TOTAL IMPUESTOS: € {total_general:,.2f}")
    print(f"  {'='*60}\n")
    
    print("⚠️  Estos impuestos NO están siendo importados como FEE/TAX")
    print(f"    Deberían restarse del Dinero Usuario como parte de las comisiones")
    print(f"\n💡 Si añadimos estos € {total_general:,.2f} a las comisiones:")
    
    from app.services.currency_service import convert_to_eur
    user = User.query.first()
    fees_bd = Transaction.query.filter_by(user_id=user.id).filter(
        Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
    ).all()
    total_fees_bd = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees_bd)
    
    print(f"    Comisiones actuales en BD: € {total_fees_bd:,.2f}")
    print(f"    Comisiones + Impuestos: € {total_fees_bd + total_general:,.2f}")
    print(f"    Incremento: € {total_general:,.2f} ({total_general/total_fees_bd*100:.2f}% más)")
    
    print("\n" + "="*80 + "\n")

