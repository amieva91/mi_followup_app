"""
Análisis profundo del cálculo de apalancamiento - VERSIÓN CORREGIDA
DeGiro NO incluye P&L No Realizado en Dinero Usuario (corrección del usuario)
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User
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
    print(f"ANÁLISIS PROFUNDO: CÁLCULO DE APALANCAMIENTO (CORREGIDO)")
    print(f"{'='*80}\n")
    
    # Datos de DeGiro
    DEGIRO = {
        'cuenta_completa': 69519.94,
        'cartera': 93748.23,
        'eur': -24228.29,  # Negativo = apalancamiento (saldo cash)
        'margen_libre': 17065.21,
        'total_bp': 46066.31
    }
    
    # Calcular valores de la app
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
    
    # Obtener métricas
    metrics = BasicMetrics.get_all_metrics(user_id, total_value, total_cost, total_pl)
    
    leverage = metrics['leverage']
    total_account = metrics['total_account']
    
    print("📊 DATOS DE DEGIRO:")
    print(f"  • Cuenta Completa:      € {DEGIRO['cuenta_completa']:>15,.2f}")
    print(f"  • Cartera:              € {DEGIRO['cartera']:>15,.2f}")
    print(f"  • EUR (saldo cash):     € {DEGIRO['eur']:>15,.2f} (negativo = apalancamiento)")
    print(f"  • Margen libre:         € {DEGIRO['margen_libre']:>15,.2f}")
    print(f"  • Total B/P:            € {DEGIRO['total_bp']:>15,.2f}")
    
    print("\n💻 DATOS DE NUESTRA APP:")
    print(f"  • Valor Total Cartera:  € {total_value:>15,.2f}")
    print(f"  • Coste Total:          € {total_cost:>15,.2f}")
    print(f"  • Dinero Usuario:       € {leverage['user_money']:>15,.2f}")
    print(f"  • Dinero Prestado:      € {leverage['broker_money']:>15,.2f}")
    print(f"  • P&L No Realizado:     € {total_account['pl_unrealized']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS: DESGLOSE DEL DINERO USUARIO")
    print("="*80)
    
    print("\n📋 Componentes del 'Dinero Usuario' (según nuestra app):")
    print(f"  • Depósitos:             € {total_account['deposits']:>15,.2f}")
    print(f"  • Retiradas:             € {total_account['withdrawals']:>15,.2f}")
    print(f"  • P&L Realizado:         € {total_account['pl_realized']:>15,.2f}")
    print(f"  • Dividendos:            € {total_account['dividends']:>15,.2f}")
    print(f"  • Comisiones:            € {total_account['fees']:>15,.2f}")
    print(f"  ────────────────────────────────────────")
    print(f"  • Dinero Usuario:        € {leverage['user_money']:>15,.2f}")
    print(f"\n  ✓ CORRECCIÓN: P&L No Realizado NO se incluye (fluctúa con precios)")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS: CÁLCULO DE APALANCAMIENTO")
    print("="*80)
    
    print(f"\n📊 Apalancamiento según DeGiro (valor absoluto): € {abs(DEGIRO['eur']):>15,.2f}")
    print(f"📊 Apalancamiento según nuestra app:              € {leverage['broker_money']:>15,.2f}")
    print(f"📊 Diferencia:                                    € {abs(DEGIRO['eur']) - leverage['broker_money']:>15,.2f}")
    
    print("\n🔍 Cómo calculamos nosotros el apalancamiento:")
    print(f"  Dinero Prestado = Coste Total - Dinero Usuario")
    print(f"  {leverage['broker_money']:,.2f} = {total_cost:,.2f} - {leverage['user_money']:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 HIPÓTESIS: ¿CÓMO CALCULA DEGIRO EL APALANCAMIENTO?")
    print("="*80)
    
    print("\n💡 HIPÓTESIS A: ¿DeGiro usa VALOR DE MERCADO en lugar de COSTE?")
    print("   (El apalancamiento se calcula sobre el valor actual, no el coste)")
    apalancamiento_valor_mercado = total_value - leverage['user_money']
    print(f"   Si: Apalancamiento = Valor Cartera - Dinero Usuario")
    print(f"   Resultado: {apalancamiento_valor_mercado:,.2f}")
    print(f"   DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"   Diferencia: {apalancamiento_valor_mercado - abs(DEGIRO['eur']):,.2f}")
    if abs(apalancamiento_valor_mercado - abs(DEGIRO['eur'])) < 1000:
        print(f"   ⚠️  Esta hipótesis NO explica la diferencia (diferencia muy grande)")
    
    print("\n💡 HIPÓTESIS B: ¿Hay diferencia en cómo se calcula 'Dinero Usuario'?")
    print("   Posibles diferencias:")
    print("   1. ¿DeGiro cuenta algunas transacciones que nosotros no?")
    print("   2. ¿DeGiro cuenta algunas transacciones de forma diferente?")
    print("   3. ¿Hay comisiones/fees que no estamos contabilizando?")
    print("   4. ¿Hay transacciones de tipos que no estamos considerando?")
    
    print("\n💡 HIPÓTESIS C: ¿DeGiro usa Cartera diferente para el cálculo?")
    print("   Si DeGiro usa su 'Cartera' (93,748.23) y nosotros (89,312.01):")
    # Si usáramos la cartera de DeGiro con nuestro dinero usuario
    apalancamiento_con_cartera_degiro = DEGIRO['cartera'] - leverage['user_money']
    print(f"   Apalancamiento = {DEGIRO['cartera']:,.2f} - {leverage['user_money']:,.2f}")
    print(f"   = {apalancamiento_con_cartera_degiro:,.2f}")
    print(f"   DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"   Diferencia: {apalancamiento_con_cartera_degiro - abs(DEGIRO['eur']):,.2f}")
    if abs(apalancamiento_con_cartera_degiro - abs(DEGIRO['eur'])) < 1000:
        print(f"   ✓ Esta hipótesis reduce significativamente la diferencia!")
    else:
        print(f"   ⚠️  Esta hipótesis NO explica la diferencia")
    
    print("\n💡 HIPÓTESIS D: ¿DeGiro calcula 'Dinero Usuario' de forma diferente?")
    # Intentar calcular qué "Dinero Usuario" usaría DeGiro para obtener su apalancamiento
    # Si: Apalancamiento = Cartera - Dinero Usuario
    # Entonces: Dinero Usuario = Cartera - Apalancamiento
    dinero_usuario_degiro_implied = DEGIRO['cartera'] - abs(DEGIRO['eur'])
    print(f"   Si DeGiro calcula: Dinero Usuario = Cartera - Apalancamiento")
    print(f"   Entonces: Dinero Usuario = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"   = {dinero_usuario_degiro_implied:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {dinero_usuario_degiro_implied - leverage['user_money']:,.2f}")
    
    print("\n💡 HIPÓTESIS E: ¿DeGiro usa 'Cuenta Completa' para calcular apalancamiento?")
    # Si DeGiro calcula: Cuenta Completa = Cartera - Apalancamiento
    # Y Cuenta Completa = Dinero Usuario (según algunas interpretaciones)
    print(f"   DeGiro muestra Cuenta Completa: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {DEGIRO['cuenta_completa'] - leverage['user_money']:,.2f}")
    if abs(DEGIRO['cuenta_completa'] - leverage['user_money']) < 1000:
        print(f"   ⚠️  ¿Podría 'Cuenta Completa' ser el 'Dinero Usuario' de DeGiro?")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS: VERIFICACIÓN DE 'CUENTA COMPLETA'")
    print("="*80)
    
    print("\n📐 DeGiro calcula Cuenta Completa como:")
    print(f"   Cuenta Completa = Cartera + EUR = {DEGIRO['cartera']:,.2f} + ({DEGIRO['eur']:,.2f})")
    print(f"   = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"   = {DEGIRO['cuenta_completa']:,.2f} ✓")
    
    print("\n📐 Si usáramos nuestros datos (estilo DeGiro):")
    cuenta_completa_app = total_value - leverage['broker_money']
    print(f"   Cuenta Completa = Cartera - Apalancamiento")
    print(f"   = {total_value:,.2f} - {leverage['broker_money']:,.2f}")
    print(f"   = {cuenta_completa_app:,.2f}")
    print(f"   DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   Diferencia: {cuenta_completa_app - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n📐 Si usáramos Cartera de DeGiro con nuestro apalancamiento:")
    cuenta_completa_cartera_degiro = DEGIRO['cartera'] - leverage['broker_money']
    print(f"   Cuenta Completa = {DEGIRO['cartera']:,.2f} - {leverage['broker_money']:,.2f}")
    print(f"   = {cuenta_completa_cartera_degiro:,.2f}")
    print(f"   DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   Diferencia: {cuenta_completa_cartera_degiro - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n" + "="*80)
    print("📝 CONCLUSIONES Y PRÓXIMOS PASOS")
    print("="*80)
    
    print("\n1. El problema principal es el cálculo del apalancamiento:")
    print(f"   • DeGiro: {abs(DEGIRO['eur']):,.2f}")
    print(f"   • App: {leverage['broker_money']:,.2f}")
    print(f"   • Diferencia: {abs(DEGIRO['eur']) - leverage['broker_money']:,.2f}")
    
    print("\n2. La diferencia en Cartera podría estar afectando:")
    print(f"   • DeGiro Cartera: {DEGIRO['cartera']:,.2f}")
    print(f"   • App Cartera: {total_value:,.2f}")
    print(f"   • Diferencia: {DEGIRO['cartera'] - total_value:,.2f}")
    print(f"   • Si usáramos Cartera de DeGiro, el apalancamiento sería:")
    print(f"     {apalancamiento_con_cartera_degiro:,.2f} (diferencia: {apalancamiento_con_cartera_degiro - abs(DEGIRO['eur']):,.2f})")
    
    print("\n3. Si 'Dinero Usuario' de DeGiro fuera igual a 'Cuenta Completa':")
    print(f"   • DeGiro Cuenta Completa: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   • Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   • Diferencia: {DEGIRO['cuenta_completa'] - leverage['user_money']:,.2f}")
    
    print("\n4. Necesitamos investigar:")
    print("   • ¿Por qué hay diferencia en Cartera? (Abengoa, precios, otros activos)")
    print("   • ¿Cómo calcula DeGiro exactamente el 'Dinero Usuario'?")
    print("   • ¿Qué base usa DeGiro para calcular el apalancamiento (coste vs valor)?")
    
    print("\n" + "="*80 + "\n")

