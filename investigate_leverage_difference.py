"""
Investigación detallada de la diferencia en el cálculo del apalancamiento
Enfoque: Entender qué podría estar añadiendo DeGiro al cálculo de "Dinero Usuario"
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.metrics.basic_metrics import BasicMetrics
from app.models.portfolio import PortfolioHolding
from app.services.currency_service import convert_to_eur

app = create_app()

with app.app_context():
    user = User.query.first()
    if not user:
        print("No hay usuarios")
        sys.exit(1)
    
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"INVESTIGACIÓN: Diferencia en Cálculo de Apalancamiento")
    print(f"{'='*80}\n")
    
    # Datos actualizados
    DEGIRO_APALANCAMIENTO = 29258.51
    DEGIRO_CARTERA = 99882.46
    DEGIRO_CUENTA_COMPLETA = 70623.95
    
    # Calcular valores reales
    all_holdings = PortfolioHolding.query.filter_by(
        user_id=user_id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    total_value = 0.0
    total_cost = 0.0
    total_pl = 0.0
    
    for h in all_holdings:
        asset = h.asset
        if asset:
            cost_eur = convert_to_eur(h.total_cost, asset.currency)
            total_cost += cost_eur
            
            if asset.current_price:
                current_value_local = h.quantity * asset.current_price
                current_value_eur = convert_to_eur(current_value_local, asset.currency)
                total_value += current_value_eur
                pl_individual = current_value_eur - cost_eur
                total_pl += pl_individual
            else:
                total_value += cost_eur
    
    metrics = BasicMetrics.get_all_metrics(user_id, total_value, total_cost, total_pl)
    leverage = metrics['leverage']
    total_account = metrics['total_account']
    
    print("📊 DATOS ACTUALES:")
    print(f"  • Cartera (App):        € {total_value:>15,.2f}")
    print(f"  • Coste Total:          € {total_cost:>15,.2f}")
    print(f"  • Dinero Usuario (App): € {leverage['user_money']:>15,.2f}")
    print(f"  • Apalancamiento (App): € {leverage['broker_money']:>15,.2f}")
    print(f"  • DeGiro Apalancamiento: € {DEGIRO_APALANCAMIENTO:>15,.2f}")
    print(f"  • Diferencia:            € {leverage['broker_money'] - DEGIRO_APALANCAMIENTO:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 1: ¿QUÉ 'DINERO USUARIO' NECESITA DEGIRO?")
    print("="*80)
    
    # Si DeGiro usa valor de mercado
    dinero_usuario_necesario_valor = total_value - DEGIRO_APALANCAMIENTO
    print(f"\n💡 Si DeGiro usa VALOR DE MERCADO:")
    print(f"   Apalancamiento = Cartera - Dinero Usuario")
    print(f"   Entonces: Dinero Usuario = Cartera - Apalancamiento")
    print(f"   = {total_value:,.2f} - {DEGIRO_APALANCAMIENTO:,.2f}")
    print(f"   = {dinero_usuario_necesario_valor:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia necesaria: {dinero_usuario_necesario_valor - leverage['user_money']:,.2f}")
    print(f"   DeGiro 'Cuenta Completa': {DEGIRO_CUENTA_COMPLETA:,.2f}")
    print(f"   ¿Coincide? {abs(dinero_usuario_necesario_valor - DEGIRO_CUENTA_COMPLETA) < 10.0}")
    
    # Si DeGiro usa coste
    dinero_usuario_necesario_coste = total_cost - DEGIRO_APALANCAMIENTO
    print(f"\n💡 Si DeGiro usa COSTE:")
    print(f"   Apalancamiento = Coste - Dinero Usuario")
    print(f"   Entonces: Dinero Usuario = Coste - Apalancamiento")
    print(f"   = {total_cost:,.2f} - {DEGIRO_APALANCAMIENTO:,.2f}")
    print(f"   = {dinero_usuario_necesario_coste:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia necesaria: {dinero_usuario_necesario_coste - leverage['user_money']:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 2: COMPONENTES DEL DINERO USUARIO ACTUAL")
    print("="*80)
    
    print(f"\n📋 Nuestro cálculo actual:")
    print(f"  • Depósitos:            € {total_account['deposits']:>15,.2f}")
    print(f"  • Retiradas:            € {total_account['withdrawals']:>15,.2f}")
    print(f"  • P&L Realizado:        € {total_account['pl_realized']:>15,.2f}")
    print(f"  • Dividendos:           € {total_account['dividends']:>15,.2f}")
    print(f"  • Comisiones:           € {total_account['fees']:>15,.2f}")
    print(f"  ────────────────────────────────────────")
    print(f"  • Total Dinero Usuario: € {leverage['user_money']:>15,.2f}")
    
    diferencia_necesaria = dinero_usuario_necesario_valor - leverage['user_money']
    print(f"\n💡 Para llegar al 'Dinero Usuario' de DeGiro (si usa valor):")
    print(f"   Necesitamos añadir: € {diferencia_necesaria:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 3: ¿QUÉ PODRÍA ESTAR FALTANDO?")
    print("="*80)
    
    # Verificar si P&L No Realizado podría ser parte
    print(f"\n💡 HIPÓTESIS A: ¿DeGiro incluye P&L No Realizado?")
    dinero_con_unrealized = leverage['user_money'] + total_account['pl_unrealized']
    print(f"   Dinero Usuario + P&L No Realizado = {leverage['user_money']:,.2f} + {total_account['pl_unrealized']:,.2f}")
    print(f"   = {dinero_con_unrealized:,.2f}")
    print(f"   Necesario (valor mercado): {dinero_usuario_necesario_valor:,.2f}")
    print(f"   Diferencia: {dinero_con_unrealized - dinero_usuario_necesario_valor:,.2f}")
    if abs(dinero_con_unrealized - dinero_usuario_necesario_valor) < 100:
        print(f"   ⚠️  ¡MUY CERCA! Esta podría ser la explicación")
    else:
        print(f"   ❌ No explica la diferencia completa")
    
    # Verificar si hay algún otro componente
    print(f"\n💡 HIPÓTESIS B: ¿DeGiro usa valor actual incluyendo P&L No Realizado?")
    print(f"   Si 'Cuenta Completa' = Dinero Usuario DeGiro")
    print(f"   Y Cuenta Completa = {DEGIRO_CUENTA_COMPLETA:,.2f}")
    print(f"   Entonces: Dinero Usuario DeGiro = {DEGIRO_CUENTA_COMPLETA:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {DEGIRO_CUENTA_COMPLETA - leverage['user_money']:,.2f}")
    
    # ¿Qué sería si añadimos P&L No Realizado?
    print(f"\n   Si añadimos P&L No Realizado: {dinero_con_unrealized:,.2f}")
    print(f"   Diferencia con Cuenta Completa: {dinero_con_unrealized - DEGIRO_CUENTA_COMPLETA:,.2f}")
    
    # Verificar todas las transacciones posibles
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 4: REVISIÓN DE TODAS LAS TRANSACCIONES")
    print("="*80)
    
    # Buscar todos los tipos de transacciones
    all_transaction_types = db.session.query(Transaction.transaction_type).distinct().all()
    print(f"\n📊 Tipos de transacciones en BD:")
    for txn_type_tuple in all_transaction_types:
        txn_type = txn_type_tuple[0]
        count = Transaction.query.filter_by(user_id=user_id, transaction_type=txn_type).count()
        if count > 0:
            total = Transaction.query.filter_by(user_id=user_id, transaction_type=txn_type).all()
            total_eur = sum(convert_to_eur(abs(t.amount), t.currency) for t in total)
            print(f"  • {txn_type:20} {count:>4} transacciones = € {total_eur:>15,.2f}")
    
    # Buscar transacciones que podrían no estar siendo contabilizadas
    print("\n💡 ¿Hay transacciones que no estamos considerando?")
    tipos_no_considerados = ['INTEREST', 'TAX', 'FX_IN', 'FX_OUT', 'CASH_SWEEP', 'WITHDRAWAL_PROCESSED']
    for tipo in tipos_no_considerados:
        count = Transaction.query.filter_by(user_id=user_id, transaction_type=tipo).count()
        if count > 0:
            txns = Transaction.query.filter_by(user_id=user_id, transaction_type=tipo).all()
            total_eur = sum(convert_to_eur(abs(t.amount), t.currency) for t in txns)
            print(f"  • {tipo}: {count} transacciones = € {total_eur:,.2f}")
    
    print("\n" + "="*80)
    print("📝 CONCLUSIÓN Y PRÓXIMOS PASOS")
    print("="*80)
    
    print("\n1. Diferencia en Apalancamiento:")
    print(f"   • App: {leverage['broker_money']:,.2f}")
    print(f"   • DeGiro: {DEGIRO_APALANCAMIENTO:,.2f}")
    print(f"   • Diferencia: {leverage['broker_money'] - DEGIRO_APALANCAMIENTO:,.2f}")
    
    print("\n2. Si DeGiro usa VALOR DE MERCADO:")
    print(f"   • Necesitaría Dinero Usuario = {dinero_usuario_necesario_valor:,.2f}")
    print(f"   • Nuestro Dinero Usuario = {leverage['user_money']:,.2f}")
    print(f"   • Diferencia: {diferencia_necesaria:,.2f}")
    
    print("\n3. Si añadimos P&L No Realizado:")
    print(f"   • Dinero Usuario + P&L No Realizado = {dinero_con_unrealized:,.2f}")
    print(f"   • Necesario (valor): {dinero_usuario_necesario_valor:,.2f}")
    print(f"   • DeGiro Cuenta Completa: {DEGIRO_CUENTA_COMPLETA:,.2f}")
    
    if abs(dinero_con_unrealized - dinero_usuario_necesario_valor) < 5000:
        print(f"\n   ⚠️  ¡La diferencia se reduce significativamente!")
        print(f"   Esto sugiere que DeGiro podría estar usando:")
        print(f"   - VALOR DE MERCADO para calcular apalancamiento")
        print(f"   - E incluyendo P&L No Realizado en 'Dinero Usuario'")
        print(f"\n   Pero el usuario dijo que NO se incluye P&L No Realizado...")
        print(f"   Necesitamos investigar más qué representa realmente 'Cuenta Completa'")
    
    print("\n4. Próximos pasos sugeridos:")
    print("   • Verificar si 'Cuenta Completa' de DeGiro realmente representa 'Dinero Usuario'")
    print("   • Investigar si hay otras transacciones o ajustes que no estamos contabilizando")
    print("   • Revisar si DeGiro calcula el apalancamiento usando valor de mercado en lugar de coste")
    
    print("\n" + "="*80 + "\n")

