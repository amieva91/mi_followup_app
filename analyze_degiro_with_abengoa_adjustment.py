"""
Análisis del apalancamiento ajustando por Abengoa (5200€)
Abengoa debe restarse de la cartera ya que ha quebrado
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
    print(f"ANÁLISIS: Cálculo de Apalancamiento AJUSTADO POR ABENGOA")
    print(f"{'='*80}\n")
    
    # Datos de DeGiro
    DEGIRO = {
        'cuenta_completa': 69519.94,
        'cartera': 93748.23,
        'eur': -24228.29,  # Negativo = apalancamiento (saldo cash)
        'margen_libre': 17065.21,
        'total_bp': 46066.31
    }
    
    # Ajuste por Abengoa
    ABENGOA_VALUE = 5200.0  # Valor de Abengoa que debe restarse
    
    print("⚠️  AJUSTE: Abengoa quebrada - € 5,200.00 deben restarse de la cartera")
    print(f"   (Valor bloqueado que DeGiro aún muestra pero que no tiene valor real)\n")
    
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
    
    # Ajustar cartera restando Abengoa
    cartera_sin_abengoa = total_value - ABENGOA_VALUE
    
    print("📊 DATOS DE DEGIRO:")
    print(f"  • Cuenta Completa:      € {DEGIRO['cuenta_completa']:>15,.2f}")
    print(f"  • Cartera:              € {DEGIRO['cartera']:>15,.2f}")
    print(f"  • EUR (saldo cash):     € {DEGIRO['eur']:>15,.2f}")
    print(f"  • Margen libre:         € {DEGIRO['margen_libre']:>15,.2f}")
    print(f"  • Total B/P:            € {DEGIRO['total_bp']:>15,.2f}")
    
    print("\n💻 DATOS DE NUESTRA APP:")
    print(f"  • Valor Total Cartera (sin ajuste):  € {total_value:>15,.2f}")
    print(f"  • Abengoa (a restar):                 € {ABENGOA_VALUE:>15,.2f}")
    print(f"  • Valor Total Cartera (ajustado):     € {cartera_sin_abengoa:>15,.2f}")
    print(f"  • Coste Total:                        € {total_cost:>15,.2f}")
    
    # Obtener métricas (usando valores sin ajuste primero para comparar)
    metrics = BasicMetrics.get_all_metrics(user_id, total_value, total_cost, total_pl)
    leverage = metrics['leverage']
    total_account = metrics['total_account']
    
    print(f"  • Dinero Usuario:                     € {leverage['user_money']:>15,.2f}")
    print(f"  • Dinero Prestado (actual):           € {leverage['broker_money']:>15,.2f}")
    print(f"  • P&L No Realizado:                   € {total_account['pl_unrealized']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 1: COMPARACIÓN DE CARTERA (AJUSTADA)")
    print("="*80)
    
    print(f"\n📊 Cartera:")
    print(f"  • DeGiro:              € {DEGIRO['cartera']:>15,.2f}")
    print(f"  • App (sin ajuste):    € {total_value:>15,.2f}")
    print(f"  • Diferencia:          € {total_value - DEGIRO['cartera']:>15,.2f}")
    print(f"\n  • App (con ajuste Abengoa): € {cartera_sin_abengoa:>15,.2f}")
    print(f"  • Diferencia (ajustada):     € {cartera_sin_abengoa - DEGIRO['cartera']:>15,.2f}")
    
    # Si DeGiro aún incluye Abengoa en su cartera, debemos restarlo también para comparar
    degiro_cartera_sin_abengoa = DEGIRO['cartera'] - ABENGOA_VALUE
    print(f"\n  • DeGiro (si restamos Abengoa): € {degiro_cartera_sin_abengoa:>15,.2f}")
    print(f"  • Diferencia final:              € {cartera_sin_abengoa - degiro_cartera_sin_abengoa:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 2: CÁLCULO DE APALANCAMIENTO CON DIFERENTES HIPÓTESIS")
    print("="*80)
    
    print("\n💡 HIPÓTESIS A: DeGiro usa VALOR DE MERCADO (con ajuste Abengoa)")
    print(f"   Si: Apalancamiento = Cartera (ajustada) - Dinero Usuario")
    print(f"   Con nuestros datos ajustados:")
    apalancamiento_hipotesis_a = cartera_sin_abengoa - leverage['user_money']
    print(f"     Apalancamiento = {cartera_sin_abengoa:,.2f} - {leverage['user_money']:,.2f}")
    print(f"     = {apalancamiento_hipotesis_a:,.2f}")
    print(f"   DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"   Diferencia: {apalancamiento_hipotesis_a - abs(DEGIRO['eur']):,.2f}")
    
    # Verificar "Cuenta Completa" con este cálculo
    cuenta_completa_hipotesis_a = cartera_sin_abengoa - apalancamiento_hipotesis_a
    print(f"\n   Si Apalancamiento = {apalancamiento_hipotesis_a:,.2f}, entonces:")
    print(f"     Cuenta Completa = {cartera_sin_abengoa:,.2f} - {apalancamiento_hipotesis_a:,.2f}")
    print(f"     = {cuenta_completa_hipotesis_a:,.2f}")
    print(f"     DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"     Diferencia: {cuenta_completa_hipotesis_a - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n💡 HIPÓTESIS B: DeGiro usa VALOR DE MERCADO pero con Abengoa")
    print(f"   (Si DeGiro aún cuenta Abengoa en su cartera)")
    print(f"   Con datos DeGiro (sin ajustar):")
    dinero_usuario_degiro_implied = DEGIRO['cartera'] - abs(DEGIRO['eur'])
    print(f"     Dinero Usuario = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"     = {dinero_usuario_degiro_implied:,.2f} (coincide con Cuenta Completa)")
    
    print(f"\n   Si ajustamos la cartera de DeGiro restando Abengoa:")
    apalancamiento_degiro_ajustado = degiro_cartera_sin_abengoa - dinero_usuario_degiro_implied
    print(f"     Apalancamiento ajustado = {degiro_cartera_sin_abengoa:,.2f} - {dinero_usuario_degiro_implied:,.2f}")
    print(f"     = {apalancamiento_degiro_ajustado:,.2f}")
    print(f"     DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"     Diferencia: {apalancamiento_degiro_ajustado - abs(DEGIRO['eur']):,.2f}")
    
    print("\n💡 HIPÓTESIS C: DeGiro usa COSTE para calcular apalancamiento")
    print(f"   Si: Apalancamiento = Coste Total - Dinero Usuario")
    print(f"   Con nuestros datos:")
    apalancamiento_hipotesis_c = total_cost - leverage['user_money']
    print(f"     Apalancamiento = {total_cost:,.2f} - {leverage['user_money']:,.2f}")
    print(f"     = {apalancamiento_hipotesis_c:,.2f}")
    print(f"   DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"   Diferencia: {apalancamiento_hipotesis_c - abs(DEGIRO['eur']):,.2f}")
    
    print("\n💡 HIPÓTESIS D: ¿DeGiro calcula de otra forma?")
    print(f"   Intentemos al revés: ¿qué 'Dinero Usuario' necesitaríamos para obtener")
    print(f"   el apalancamiento de DeGiro?")
    print(f"\n   Si: Apalancamiento DeGiro = {abs(DEGIRO['eur']):,.2f}")
    print(f"   Y usamos Cartera ajustada: {cartera_sin_abengoa:,.2f}")
    print(f"   Entonces: Dinero Usuario necesario = {cartera_sin_abengoa:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    dinero_usuario_necesario = cartera_sin_abengoa - abs(DEGIRO['eur'])
    print(f"   = {dinero_usuario_necesario:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {dinero_usuario_necesario - leverage['user_money']:,.2f}")
    
    print(f"\n   ¿Qué componentes tendríamos que ajustar?")
    print(f"     Necesitamos añadir: € {dinero_usuario_necesario - leverage['user_money']:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 3: VERIFICACIÓN DE 'CUENTA COMPLETA' CON AJUSTE")
    print("="*80)
    
    print("\n📐 DeGiro calcula Cuenta Completa como:")
    print(f"   Cuenta Completa = Cartera + EUR")
    print(f"   {DEGIRO['cuenta_completa']:,.2f} = {DEGIRO['cartera']:,.2f} + ({DEGIRO['eur']:,.2f})")
    print(f"   = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"   = {DEGIRO['cuenta_completa']:,.2f} ✓")
    
    print(f"\n📐 Si ajustamos la cartera de DeGiro (restando Abengoa):")
    print(f"   Cuenta Completa ajustada = {degiro_cartera_sin_abengoa:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    cuenta_completa_degiro_ajustada = degiro_cartera_sin_abengoa - abs(DEGIRO['eur'])
    print(f"   = {cuenta_completa_degiro_ajustada:,.2f}")
    print(f"   DeGiro muestra (sin ajuste): {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   Diferencia: {cuenta_completa_degiro_ajustada - DEGIRO['cuenta_completa']:,.2f}")
    print(f"   (La diferencia es exactamente -Abengoa: -{ABENGOA_VALUE:,.2f})")
    
    print(f"\n📐 Con nuestros datos (cartera ajustada):")
    cuenta_completa_app_ajustada = cartera_sin_abengoa - apalancamiento_hipotesis_a
    print(f"   Si usamos Hipótesis A (valor mercado):")
    print(f"     Cuenta Completa = {cartera_sin_abengoa:,.2f} - {apalancamiento_hipotesis_a:,.2f}")
    print(f"     = {cuenta_completa_app_ajustada:,.2f}")
    print(f"   DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   Diferencia: {cuenta_completa_app_ajustada - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n" + "="*80)
    print("📝 CONCLUSIONES Y REFLEXIONES")
    print("="*80)
    
    print("\n1. Ajuste por Abengoa:")
    print(f"   • Valor a restar: € {ABENGOA_VALUE:,.2f}")
    print(f"   • Cartera app (ajustada): € {cartera_sin_abengoa:,.2f}")
    print(f"   • Si DeGiro también tiene Abengoa, su cartera ajustada sería: € {degiro_cartera_sin_abengoa:,.2f}")
    print(f"   • Diferencia entre carteras ajustadas: € {cartera_sin_abengoa - degiro_cartera_sin_abengoa:,.2f}")
    
    print("\n2. Apalancamiento:")
    print(f"   • DeGiro muestra: € {abs(DEGIRO['eur']):,.2f}")
    print(f"   • Si usamos Hipótesis A (valor mercado ajustado): € {apalancamiento_hipotesis_a:,.2f}")
    print(f"   • Diferencia: € {apalancamiento_hipotesis_a - abs(DEGIRO['eur']):,.2f}")
    
    print("\n3. Cuenta Completa:")
    print(f"   • DeGiro muestra: € {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   • Si DeGiro ajustara Abengoa, sería: € {cuenta_completa_degiro_ajustada:,.2f}")
    print(f"   • Con nuestros datos (Hipótesis A ajustada): € {cuenta_completa_app_ajustada:,.2f}")
    print(f"   • Diferencia: € {cuenta_completa_app_ajustada - cuenta_completa_degiro_ajustada:,.2f}")
    
    print("\n4. El problema principal:")
    print("   Aún no sabemos EXACTAMENTE cómo calcula DeGiro el apalancamiento.")
    print("   Las hipótesis nos acercan pero no explican completamente la diferencia.")
    
    print("\n5. Preguntas pendientes:")
    print("   • ¿DeGiro realmente cuenta Abengoa en su cartera?")
    print("   • ¿DeGiro calcula 'Dinero Usuario' de forma diferente?")
    print("   • ¿Hay transacciones o ajustes que no estamos considerando?")
    print("   • ¿El cálculo del apalancamiento usa alguna fórmula diferente?")
    
    print("\n" + "="*80 + "\n")

