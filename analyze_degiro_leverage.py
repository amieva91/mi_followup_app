"""
Análisis profundo del cálculo de apalancamiento comparando con DeGiro
SIN hacer cambios en el código, solo investigación
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.metrics.basic_metrics import BasicMetrics
from app.models.portfolio import PortfolioHolding
from app.services.currency_service import convert_to_eur
from sqlalchemy import func

app = create_app()

with app.app_context():
    user = User.query.first()
    if not user:
        print("No hay usuarios")
        sys.exit(1)
    
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"ANÁLISIS PROFUNDO: CÁLCULO DE APALANCAMIENTO (DeGiro vs App)")
    print(f"{'='*80}\n")
    
    # Datos de DeGiro
    DEGIRO = {
        'cuenta_completa': 69519.94,
        'cartera': 93748.23,
        'eur': -24228.29,  # Negativo = apalancamiento
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
    print(f"  • EUR (apalancamiento): € {DEGIRO['eur']:>15,.2f}")
    print(f"  • Margen libre:         € {DEGIRO['margen_libre']:>15,.2f}")
    print(f"  • Total B/P:            € {DEGIRO['total_bp']:>15,.2f}")
    
    print("\n💻 DATOS DE NUESTRA APP:")
    print(f"  • Valor Total Cartera:  € {total_value:>15,.2f}")
    print(f"  • Coste Total:          € {total_cost:>15,.2f}")
    print(f"  • Dinero Usuario:       € {leverage['user_money']:>15,.2f}")
    print(f"  • Dinero Prestado:      € {leverage['broker_money']:>15,.2f}")
    print(f"  • P&L No Realizado:     € {total_account['pl_unrealized']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 1: RELACIONES DE DEGIRO")
    print("="*80)
    
    # Relación 1: Cuenta Completa = Cartera + EUR
    calc1 = DEGIRO['cartera'] + DEGIRO['eur']
    print(f"\n✓ Verificación: Cuenta Completa = Cartera + EUR")
    print(f"  {DEGIRO['cartera']:,.2f} + ({DEGIRO['eur']:,.2f}) = {calc1:,.2f}")
    print(f"  DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f} {'✓' if abs(calc1 - DEGIRO['cuenta_completa']) < 0.01 else '✗'}")
    
    # Relación 2: EUR = Cuenta Completa - Cartera
    calc2 = DEGIRO['cuenta_completa'] - DEGIRO['cartera']
    print(f"\n✓ Verificación: EUR = Cuenta Completa - Cartera")
    print(f"  {DEGIRO['cuenta_completa']:,.2f} - {DEGIRO['cartera']:,.2f} = {calc2:,.2f}")
    print(f"  DeGiro muestra EUR: {DEGIRO['eur']:,.2f} {'✓' if abs(calc2 - DEGIRO['eur']) < 0.01 else '✗'}")
    
    # Relación 3: ¿Qué es Cuenta Completa?
    # Si Cuenta Completa = Cartera - Apalancamiento
    # Entonces: Apalancamiento = Cartera - Cuenta Completa
    apalancamiento_degiro = DEGIRO['cartera'] - DEGIRO['cuenta_completa']
    print(f"\n✓ Cálculo: Apalancamiento (absoluto) = Cartera - Cuenta Completa")
    print(f"  {DEGIRO['cartera']:,.2f} - {DEGIRO['cuenta_completa']:,.2f} = {apalancamiento_degiro:,.2f}")
    print(f"  DeGiro muestra EUR (negativo): {DEGIRO['eur']:,.2f}")
    print(f"  Relación: EUR = -Apalancamiento {'✓' if abs(apalancamiento_degiro + DEGIRO['eur']) < 0.01 else '✗'}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 2: INTERPRETACIÓN DE 'Cuenta Completa'")
    print("="*80)
    
    print("\n💡 HIPO TESIS 1: Cuenta Completa = Valor de la cartera sin apalancamiento")
    print(f"  Cuenta Completa = Cartera - Apalancamiento")
    print(f"  {DEGIRO['cuenta_completa']:,.2f} = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"  Esto representaría el valor 'real' del usuario (lo que ha aportado + ganancias)")
    
    print("\n💡 HIPÓTESIS 2: Cuenta Completa = Dinero del usuario + P&L no realizado")
    # Intentar calcular con nuestros datos
    cuenta_completa_h2 = leverage['user_money'] + total_account['pl_unrealized']
    print(f"  Con nuestros datos: {leverage['user_money']:,.2f} + {total_account['pl_unrealized']:,.2f} = {cuenta_completa_h2:,.2f}")
    print(f"  DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"  Diferencia: {cuenta_completa_h2 - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n💡 HIPÓTESIS 3: Cuenta Completa = Cartera - Apalancamiento")
    cuenta_completa_h3 = total_value - leverage['broker_money']
    print(f"  Con nuestros datos: {total_value:,.2f} - {leverage['broker_money']:,.2f} = {cuenta_completa_h3:,.2f}")
    print(f"  DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"  Diferencia: {cuenta_completa_h3 - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 3: DESGLOSE DEL DINERO DEL USUARIO")
    print("="*80)
    
    print("\n📋 Componentes del 'Dinero Usuario' (según nuestra app):")
    print(f"  • Depósitos:             € {total_account['deposits']:>15,.2f}")
    print(f"  • Retiradas:             € {total_account['withdrawals']:>15,.2f}")
    print(f"  • P&L Realizado:         € {total_account['pl_realized']:>15,.2f}")
    print(f"  • Dividendos:            € {total_account['dividends']:>15,.2f}")
    print(f"  • Comisiones:            € {total_account['fees']:>15,.2f}")
    print(f"  ────────────────────────────────────────")
    print(f"  • Dinero Usuario:        € {leverage['user_money']:>15,.2f}")
    
    print("\n💡 ¿Podría DeGiro estar calculando 'Dinero Usuario' de forma diferente?")
    print("  Posibles diferencias:")
    print("  1. ¿Incluye P&L No Realizado en 'Dinero Usuario'?")
    print("  2. ¿Usa valor de mercado en lugar de coste para calcular apalancamiento?")
    print("  3. ¿Tiene en cuenta transacciones que nosotros no?")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 4: COMPARACIÓN DE APALANCAMIENTO")
    print("="*80)
    
    print(f"\n📊 Apalancamiento según DeGiro (valor absoluto): € {abs(DEGIRO['eur']):,.2f}")
    print(f"📊 Apalancamiento según nuestra app:              € {leverage['broker_money']:,.2f}")
    print(f"📊 Diferencia:                                    € {abs(DEGIRO['eur']) - leverage['broker_money']:,.2f}")
    
    print("\n🔍 ¿Cómo calculamos nosotros el apalancamiento?")
    print(f"  Dinero Prestado = Coste Total - Dinero Usuario")
    print(f"  {leverage['broker_money']:,.2f} = {total_cost:,.2f} - {leverage['user_money']:,.2f}")
    
    print("\n💡 HIPÓTESIS A: ¿DeGiro usa valor de mercado en lugar de coste?")
    apalancamiento_valor_mercado = total_value - leverage['user_money']
    print(f"  Si usáramos: Apalancamiento = Valor Cartera - Dinero Usuario")
    print(f"  Resultado: {apalancamiento_valor_mercado:,.2f}")
    print(f"  DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"  Diferencia: {apalancamiento_valor_mercado - abs(DEGIRO['eur']):,.2f}")
    
    print("\n💡 HIPÓTESIS B: ¿DeGiro incluye P&L No Realizado en 'Dinero Usuario'?")
    dinero_usuario_con_unrealized = leverage['user_money'] + total_account['pl_unrealized']
    apalancamiento_con_unrealized = total_cost - dinero_usuario_con_unrealized
    print(f"  Si: Dinero Usuario = {leverage['user_money']:,.2f} + {total_account['pl_unrealized']:,.2f} = {dinero_usuario_con_unrealized:,.2f}")
    print(f"  Entonces: Apalancamiento = {total_cost:,.2f} - {dinero_usuario_con_unrealized:,.2f} = {apalancamiento_con_unrealized:,.2f}")
    print(f"  DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"  Diferencia: {apalancamiento_con_unrealized - abs(DEGIRO['eur']):,.2f}")
    
    print("\n💡 HIPÓTESIS C: ¿DeGiro usa valor de mercado e incluye P&L No Realizado?")
    apalancamiento_hipotesis_c = total_value - dinero_usuario_con_unrealized
    print(f"  Apalancamiento = Valor Cartera - (Dinero Usuario + P&L No Realizado)")
    print(f"  = {total_value:,.2f} - {dinero_usuario_con_unrealized:,.2f} = {apalancamiento_hipotesis_c:,.2f}")
    print(f"  DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"  Diferencia: {apalancamiento_hipotesis_c - abs(DEGIRO['eur']):,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 5: VERIFICACIÓN DE 'Cuenta Completa' CON DIFERENTES FÓRMULAS")
    print("="*80)
    
    formulas = [
        ("Cartera - Apalancamiento (coste)", total_value - leverage['broker_money']),
        ("Cartera - Apalancamiento (valor mercado)", total_value - apalancamiento_valor_mercado),
        ("Dinero Usuario + P&L No Realizado", leverage['user_money'] + total_account['pl_unrealized']),
        ("Cartera - (Cartera - Dinero Usuario)", leverage['user_money']),
    ]
    
    print(f"\n{'Fórmula':<50} {'Resultado':>20} {'Diferencia con DeGiro':>25}")
    print("-" * 95)
    for formula_name, result in formulas:
        diff = result - DEGIRO['cuenta_completa']
        print(f"{formula_name:<50} € {result:>15,.2f} € {diff:>20,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 6: DIFERENCIAS EN CARTERA")
    print("="*80)
    
    diff_cartera = total_value - DEGIRO['cartera']
    print(f"\n  DeGiro Cartera:    € {DEGIRO['cartera']:>15,.2f}")
    print(f"  App Cartera:       € {total_value:>15,.2f}")
    print(f"  Diferencia:        € {diff_cartera:>15,.2f}")
    print(f"\n  Posibles causas:")
    print(f"  1. Abengoa vendida en app pero aún en DeGiro (~5,200€)")
    print(f"  2. Diferencias en precios de mercado")
    print(f"  3. Activos no contabilizados en una u otra parte")
    
    print("\n" + "="*80)
    print("📝 CONCLUSIONES")
    print("="*80)
    
    print("\n1. DeGiro calcula 'Cuenta Completa' como:")
    print("   Cuenta Completa = Cartera + EUR = Cartera - Apalancamiento")
    print(f"   {DEGIRO['cuenta_completa']:,.2f} = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    
    print("\n2. Nuestro apalancamiento difiere significativamente:")
    print(f"   DeGiro: {abs(DEGIRO['eur']):,.2f} | App: {leverage['broker_money']:,.2f} | Diferencia: {abs(DEGIRO['eur']) - leverage['broker_money']:,.2f}")
    
    print("\n3. Nuestra 'Cuenta Completa' (estilo DeGiro) sería:")
    cuenta_completa_app = total_value - leverage['broker_money']
    print(f"   {cuenta_completa_app:,.2f} vs DeGiro {DEGIRO['cuenta_completa']:,.2f} (diferencia: {cuenta_completa_app - DEGIRO['cuenta_completa']:,.2f})")
    
    print("\n4. El problema principal parece estar en el cálculo del apalancamiento.")
    print("   Necesitamos investigar qué usa DeGiro como base para calcular el apalancamiento.")
    
    print("\n" + "="*80 + "\n")

