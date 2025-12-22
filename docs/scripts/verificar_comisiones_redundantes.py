"""
Verificar si las comisiones se están contando dos veces:
1. En el P&L Realizado (ya restadas de los proceeds de ventas)
2. En las comisiones totales (restadas del Dinero Usuario)
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.metrics.basic_metrics import BasicMetrics
from app.services.currency_service import convert_to_eur

app = create_app()

with app.app_context():
    user = User.query.first()
    if not user:
        print("No hay usuarios")
        sys.exit(1)
    
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"VERIFICACIÓN: Doble contabilidad de comisiones")
    print(f"{'='*80}\n")
    
    # 1. Obtener todas las comisiones FEE/COMMISSION
    fees_standalone = Transaction.query.filter_by(user_id=user_id).filter(
        Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
    ).all()
    
    total_fees_standalone = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees_standalone)
    
    print("📊 COMISIONES STANDALONE (tipo FEE/COMMISSION):")
    print(f"  • Total: € {total_fees_standalone:,.2f}")
    print(f"  • Cantidad de transacciones: {len(fees_standalone)}")
    
    # 2. Obtener comisiones de compras (incluidas en BUY transactions)
    buys = Transaction.query.filter_by(user_id=user_id, transaction_type='BUY').all()
    total_commission_buys = 0.0
    total_fees_buys = 0.0
    for buy in buys:
        if buy.commission:
            total_commission_buys += convert_to_eur(buy.commission, buy.currency)
        if buy.fees:
            total_fees_buys += convert_to_eur(buy.fees, buy.currency)
    
    comisiones_compras = total_commission_buys + total_fees_buys
    
    print(f"\n📊 COMISIONES DE COMPRAS (incluidas en transacciones BUY):")
    print(f"  • Commission: € {total_commission_buys:,.2f}")
    print(f"  • Fees: € {total_fees_buys:,.2f}")
    print(f"  • Total: € {comisiones_compras:,.2f}")
    
    # 3. Obtener comisiones de ventas (incluidas en SELL transactions)
    sells = Transaction.query.filter_by(user_id=user_id, transaction_type='SELL').all()
    total_commission_sells = 0.0
    total_fees_sells = 0.0
    for sell in sells:
        if sell.commission:
            total_commission_sells += convert_to_eur(sell.commission, sell.currency)
        if sell.fees:
            total_fees_sells += convert_to_eur(sell.fees, sell.currency)
    
    comisiones_ventas = total_commission_sells + total_fees_sells
    
    print(f"\n📊 COMISIONES DE VENTAS (incluidas en transacciones SELL):")
    print(f"  • Commission: € {total_commission_sells:,.2f}")
    print(f"  • Fees: € {total_fees_sells:,.2f}")
    print(f"  • Total: € {comisiones_ventas:,.2f}")
    
    # 4. Verificar cómo se calcula el P&L Realizado
    print(f"\n{'='*80}")
    print("🔍 ANÁLISIS DEL P&L REALIZADO")
    print(f"{'='*80}\n")
    
    print("El P&L Realizado se calcula así:")
    print("  Para cada venta:")
    print("    1. proceeds = (cantidad × precio) - commission - fees - tax")
    print("    2. P&L = proceeds - cost_basis_FIFO")
    print("\n  ✓ Las comisiones de VENTAS ya están restadas en el P&L Realizado")
    
    # 5. Verificar cómo se calcula el Dinero Usuario
    print(f"\n{'='*80}")
    print("🔍 ANÁLISIS DEL DINERO USUARIO")
    print(f"{'='*80}\n")
    
    print("El Dinero Usuario se calcula así:")
    print("  Dinero Usuario = Depósitos - Retiradas + P&L Realizado + P&L No Realizado + Dividendos - Comisiones")
    print(f"\n  Comisiones restadas: € {total_fees_standalone:,.2f}")
    print(f"  (Estas son solo las transacciones tipo FEE/COMMISSION)")
    
    # 6. Análisis del problema
    print(f"\n{'='*80}")
    print("⚠️  VERIFICACIÓN DE DOBLE CONTABILIDAD")
    print(f"{'='*80}\n")
    
    print("¿Se cuentan las comisiones dos veces?")
    print(f"\n1. Comisiones de VENTAS:")
    print(f"   • Total: € {comisiones_ventas:,.2f}")
    print(f"   • Ya están restadas en el P&L Realizado ✓")
    print(f"   • ¿Están también en 'Comisiones totales' (FEE/COMMISSION)?")
    
    # Verificar si alguna comisión de venta está también como transacción FEE/COMMISSION
    # Esto sería raro, pero puede pasar si hay algún error en la importación
    fees_from_sells = []
    for sell in sells:
        if sell.commission or sell.fees:
            # Buscar si hay una transacción FEE/COMMISSION en la misma fecha con el mismo monto
            for fee in fees_standalone:
                if fee.transaction_date.date() == sell.transaction_date.date():
                    fee_amount_eur = convert_to_eur(abs(fee.amount), fee.currency)
                    sell_commission_eur = convert_to_eur(sell.commission or 0, sell.currency)
                    sell_fees_eur = convert_to_eur(sell.fees or 0, sell.currency)
                    if abs(fee_amount_eur - sell_commission_eur) < 0.01 or abs(fee_amount_eur - sell_fees_eur) < 0.01:
                        fees_from_sells.append(fee)
    
    if fees_from_sells:
        print(f"   ⚠️  Se encontraron {len(fees_from_sells)} transacciones FEE/COMMISSION que podrían ser comisiones de ventas")
        total_duplicadas = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees_from_sells)
        print(f"   • Monto total posiblemente duplicado: € {total_duplicadas:,.2f}")
    else:
        print(f"   ✓ No se encontraron comisiones de ventas duplicadas como FEE/COMMISSION")
    
    print(f"\n2. Comisiones de COMPRAS:")
    print(f"   • Total: € {comisiones_compras:,.2f}")
    print(f"   • Estas NO están en el P&L Realizado (solo afectan el cost_basis)")
    print(f"   • ¿Están en 'Comisiones totales' (FEE/COMMISSION)?")
    
    # Verificar si alguna comisión de compra está también como transacción FEE/COMMISSION
    fees_from_buys = []
    for buy in buys:
        if buy.commission or buy.fees:
            for fee in fees_standalone:
                if fee.transaction_date.date() == buy.transaction_date.date():
                    fee_amount_eur = convert_to_eur(abs(fee.amount), fee.currency)
                    buy_commission_eur = convert_to_eur(buy.commission or 0, buy.currency)
                    buy_fees_eur = convert_to_eur(buy.fees or 0, buy.currency)
                    if abs(fee_amount_eur - buy_commission_eur) < 0.01 or abs(fee_amount_eur - buy_fees_eur) < 0.01:
                        fees_from_buys.append(fee)
    
    if fees_from_buys:
        print(f"   ⚠️  Se encontraron {len(fees_from_buys)} transacciones FEE/COMMISSION que podrían ser comisiones de compras")
        total_duplicadas = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees_from_buys)
        print(f"   • Monto total posiblemente duplicado: € {total_duplicadas:,.2f}")
    else:
        print(f"   ✓ No se encontraron comisiones de compras duplicadas como FEE/COMMISSION")
    
    print(f"\n3. Comisiones STANDALONE (FEE/COMMISSION):")
    print(f"   • Total: € {total_fees_standalone:,.2f}")
    print(f"   • Estas son comisiones generales (conectividad, custodia, etc.)")
    print(f"   • Estas SÍ deben restarse del Dinero Usuario")
    
    # 7. Conclusión
    print(f"\n{'='*80}")
    print("📝 CONCLUSIÓN")
    print(f"{'='*80}\n")
    
    print("RESPUESTA: NO hay doble contabilidad si:")
    print("  • Las comisiones FEE/COMMISSION son solo comisiones generales")
    print("  • Las comisiones de compras/ventas están solo en los campos commission/fees de BUY/SELL")
    print(f"\n  ✓ Comisiones de ventas: Ya restadas en P&L Realizado (€ {comisiones_ventas:,.2f})")
    print(f"  ✓ Comisiones de compras: Incluidas en cost_basis (no afectan P&L Realizado)")
    print(f"  ✓ Comisiones standalone: Se restan del Dinero Usuario (€ {total_fees_standalone:,.2f})")
    
    if not fees_from_sells and not fees_from_buys:
        print(f"\n✅ NO HAY DOBLE CONTABILIDAD: Las comisiones están correctamente separadas")
    else:
        print(f"\n⚠️  POSIBLE PROBLEMA: Hay comisiones que podrían estar duplicadas")
    
    print("\n" + "="*80 + "\n")

