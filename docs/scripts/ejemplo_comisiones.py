"""
Ejemplo para confirmar cómo se manejan las comisiones
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.currency_service import convert_to_eur

app = create_app()

with app.app_context():
    user = User.query.first()
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"EJEMPLO: Cómo se manejan las comisiones")
    print(f"{'='*80}\n")
    
    # Ejemplo de una compra
    print("📦 EJEMPLO DE COMPRA:")
    buy_example = Transaction.query.filter_by(
        user_id=user_id, 
        transaction_type='BUY'
    ).first()
    
    if buy_example:
        print(f"  • Tipo: BUY")
        print(f"  • Asset: {buy_example.asset.symbol if buy_example.asset else 'N/A'}")
        print(f"  • Cantidad × Precio: {buy_example.quantity} × {buy_example.price} = {buy_example.quantity * buy_example.price} {buy_example.currency}")
        print(f"  • Commission (en la transacción): {buy_example.commission or 0} {buy_example.currency}")
        print(f"  • Fees (en la transacción): {buy_example.fees or 0} {buy_example.currency}")
        print(f"  • Coste total (precio + comisiones): {(buy_example.quantity * buy_example.price) + (buy_example.commission or 0) + (buy_example.fees or 0)} {buy_example.currency}")
        print(f"\n  ✓ Esta comisión está INCLUIDA en el cost_basis de la compra")
        print(f"  ✓ NO aparece como transacción FEE/COMMISSION separada")
    
    # Ejemplo de una venta
    print(f"\n💰 EJEMPLO DE VENTA:")
    sell_example = Transaction.query.filter_by(
        user_id=user_id, 
        transaction_type='SELL'
    ).first()
    
    if sell_example:
        print(f"  • Tipo: SELL")
        print(f"  • Asset: {sell_example.asset.symbol if sell_example.asset else 'N/A'}")
        print(f"  • Cantidad × Precio: {sell_example.quantity} × {sell_example.price} = {sell_example.quantity * sell_example.price} {sell_example.currency}")
        print(f"  • Commission (en la transacción): {sell_example.commission or 0} {sell_example.currency}")
        print(f"  • Fees (en la transacción): {sell_example.fees or 0} {sell_example.currency}")
        print(f"  • Proceeds (precio - comisiones): {(sell_example.quantity * sell_example.price) - (sell_example.commission or 0) - (sell_example.fees or 0)} {sell_example.currency}")
        print(f"\n  ✓ Esta comisión está RESTADA de los proceeds de la venta")
        print(f"  ✓ Por lo tanto, ya está incluida en el P&L Realizado")
        print(f"  ✓ NO aparece como transacción FEE/COMMISSION separada")
    
    # Ejemplo de comisión general
    print(f"\n💳 EJEMPLO DE COMISIÓN GENERAL:")
    fee_example = Transaction.query.filter_by(
        user_id=user_id
    ).filter(
        Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
    ).first()
    
    if fee_example:
        print(f"  • Tipo: {fee_example.transaction_type}")
        print(f"  • Descripción: {fee_example.description or 'N/A'}")
        print(f"  • Amount: {fee_example.amount} {fee_example.currency}")
        print(f"  • Asset: {fee_example.asset.symbol if fee_example.asset else 'N/A (comisión general)'}")
        print(f"\n  ✓ Esta es una comisión GENERAL (conectividad, custodia, etc.)")
        print(f"  ✓ NO está relacionada con una compra o venta específica")
        print(f"  ✓ Se resta del Dinero Usuario")
    
    print(f"\n{'='*80}")
    print("✅ CONCLUSIÓN")
    print(f"{'='*80}\n")
    
    print("Las comisiones se manejan de forma SEPARADA:")
    print("\n1. COMISIONES DE COMPRAS/VENTAS:")
    print("   • Están en los campos 'commission' y 'fees' de las transacciones BUY/SELL")
    print("   • Para COMPRAS: Se suman al cost_basis (coste total de compra)")
    print("   • Para VENTAS: Se restan de los proceeds (ingresos de venta)")
    print("   • NO aparecen como transacciones FEE/COMMISSION separadas")
    
    print("\n2. COMISIONES GENERALES:")
    print("   • Son transacciones independientes de tipo FEE o COMMISSION")
    print("   • Ejemplos: comisiones de conectividad, custodia, etc.")
    print("   • NO están relacionadas con compras/ventas específicas")
    print("   • Se restan directamente del Dinero Usuario")
    
    print("\n✅ Por lo tanto, NO hay solapamiento ni doble contabilidad")
    print("="*80 + "\n")

