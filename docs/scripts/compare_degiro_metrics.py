"""
Script para comparar métricas de DeGiro con métricas de la aplicación
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
    # Obtener el primer usuario (ajustar si hay múltiples usuarios)
    user = User.query.first()
    if not user:
        print("No hay usuarios en la base de datos")
        sys.exit(1)
    
    user_id = user.id
    print(f"\n{'='*80}")
    print(f"COMPARACIÓN DE MÉTRICAS: DeGiro vs Aplicación")
    print(f"{'='*80}\n")
    
    # 1. Calcular valores del portfolio actual (como en dashboard)
    from collections import defaultdict
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
    
    # 2. Obtener todas las métricas
    metrics = BasicMetrics.get_all_metrics(
        user_id,
        total_value,
        total_cost,
        total_pl
    )
    
    # 3. Datos de DeGiro (de la captura)
    DEGIRO_DATA = {
        'cuenta_completa': 69519.94,
        'cartera': 93748.23,
        'eur': -24228.29,  # Negativo = apalancamiento
        'margen_libre': 17065.21,
        'total_bp': 46066.31
    }
    
    # 4. Datos de nuestra aplicación
    APP_DATA = {
        'valor_real_cuenta': metrics['total_account']['total_account_value'],
        'valor_total_cartera': total_value,
        'dinero_prestado': metrics['leverage']['broker_money'],
        'total_pl': metrics['total_pl']['total_pl'],
        'coste_total': total_cost
    }
    
    # 5. Calcular "Cuenta Completa" según nuestra interpretación
    # En DeGiro: Cuenta Completa = Cartera - EUR (apalancamiento)
    # EUR negativo = apalancamiento, así que:
    # Cuenta Completa = Cartera - (-Apalancamiento) = Cartera + Apalancamiento
    # Pero EUR es negativo, así que: Cuenta Completa = Cartera + |EUR|
    calculated_cuenta_completa = APP_DATA['valor_total_cartera'] + abs(APP_DATA['dinero_prestado']) if APP_DATA['dinero_prestado'] < 0 else APP_DATA['valor_total_cartera'] - APP_DATA['dinero_prestado']
    
    # 6. Mostrar comparación
    print("📊 DATOS DE DEGIRO (de la captura):")
    print(f"  • Cuenta Completa:      € {DEGIRO_DATA['cuenta_completa']:>15,.2f}")
    print(f"  • Cartera:              € {DEGIRO_DATA['cartera']:>15,.2f}")
    print(f"  • EUR (apalancamiento): € {DEGIRO_DATA['eur']:>15,.2f}")
    print(f"  • Margen libre:         € {DEGIRO_DATA['margen_libre']:>15,.2f}")
    print(f"  • Total B/P:            € {DEGIRO_DATA['total_bp']:>15,.2f}")
    
    print("\n💻 DATOS DE NUESTRA APLICACIÓN:")
    print(f"  • Valor Real Cuenta:    € {APP_DATA['valor_real_cuenta']:>15,.2f}")
    print(f"  • Valor Total Cartera:  € {APP_DATA['valor_total_cartera']:>15,.2f}")
    print(f"  • Dinero Prestado:      € {APP_DATA['dinero_prestado']:>15,.2f}")
    print(f"  • P&L Total:            € {APP_DATA['total_pl']:>15,.2f}")
    print(f"  • Coste Total:          € {APP_DATA['coste_total']:>15,.2f}")
    
    print("\n🔍 ANÁLISIS:")
    print(f"  • Diferencia Cartera:            € {APP_DATA['valor_total_cartera'] - DEGIRO_DATA['cartera']:>15,.2f}")
    print(f"  • Diferencia Apalancamiento:     € {APP_DATA['dinero_prestado'] - abs(DEGIRO_DATA['eur']):>15,.2f}")
    print(f"  • Diferencia P&L Total:          € {APP_DATA['total_pl'] - DEGIRO_DATA['total_bp']:>15,.2f}")
    
    # 7. Intentar calcular "Cuenta Completa" como DeGiro
    # Si EUR es negativo (apalancamiento), entonces:
    # Cuenta Completa = Cartera - Apalancamiento
    # Pero EUR ya es negativo, así que: Cuenta Completa = Cartera - EUR = Cartera - (-24228.29) = Cartera + 24228.29
    degiro_cuenta_completa_calc = DEGIRO_DATA['cartera'] - DEGIRO_DATA['eur']  # 93748.23 - (-24228.29) = 117976.52
    print(f"\n  • DeGiro: Cuenta Completa = Cartera - EUR")
    print(f"    = {DEGIRO_DATA['cartera']:,.2f} - ({DEGIRO_DATA['eur']:,.2f})")
    print(f"    = {DEGIRO_DATA['cartera']:,.2f} - {DEGIRO_DATA['eur']:,.2f}")
    print(f"    = {DEGIRO_DATA['cuenta_completa']:,.2f} ✓")
    
    # Intentar calcular "Cuenta Completa" con nuestros datos
    app_cuenta_completa_calc = APP_DATA['valor_total_cartera'] - APP_DATA['dinero_prestado']
    print(f"\n  • App: Cuenta Completa calculada = Cartera - Dinero Prestado")
    print(f"    = {APP_DATA['valor_total_cartera']:,.2f} - ({APP_DATA['dinero_prestado']:,.2f})")
    print(f"    = {APP_DATA['valor_total_cartera']:,.2f} - {APP_DATA['dinero_prestado']:,.2f}")
    print(f"    = {app_cuenta_completa_calc:,.2f}")
    print(f"  • DeGiro Cuenta Completa:        € {DEGIRO_DATA['cuenta_completa']:>15,.2f}")
    print(f"  • Diferencia:                    € {app_cuenta_completa_calc - DEGIRO_DATA['cuenta_completa']:>15,.2f}")
    
    # 8. Desglose de componentes
    print("\n📋 DESGLOSE DE COMPONENTES (Aplicación):")
    leverage = metrics['leverage']
    total_account = metrics['total_account']
    print(f"  • Depósitos:                     € {total_account['deposits']:>15,.2f}")
    print(f"  • Retiradas:                     € {total_account['withdrawals']:>15,.2f}")
    print(f"  • P&L Realizado:                 € {total_account['pl_realized']:>15,.2f}")
    print(f"  • P&L No Realizado:              € {total_account['pl_unrealized']:>15,.2f}")
    print(f"  • Dividendos:                    € {total_account['dividends']:>15,.2f}")
    print(f"  • Comisiones:                    € {total_account['fees']:>15,.2f}")
    print(f"  • Dinero Usuario:                € {leverage['user_money']:>15,.2f}")
    
    # 9. Fórmulas
    print("\n📐 FÓRMULAS DE NUESTRA APP:")
    print(f"  • Dinero Usuario = Depósitos - Retiradas + P&L Realizado + Dividendos - Comisiones")
    print(f"    = {total_account['deposits']:,.2f} - {total_account['withdrawals']:,.2f} + {total_account['pl_realized']:,.2f} + {total_account['dividends']:,.2f} - {total_account['fees']:,.2f}")
    print(f"    = {leverage['user_money']:,.2f}")
    print(f"\n  • Dinero Prestado = Coste Total - Dinero Usuario")
    print(f"    = {total_cost:,.2f} - {leverage['user_money']:,.2f}")
    print(f"    = {leverage['broker_money']:,.2f}")
    print(f"\n  • Valor Real Cuenta (App) = Dinero Usuario + P&L No Realizado")
    print(f"    = {leverage['user_money']:,.2f} + {total_account['pl_unrealized']:,.2f}")
    print(f"    = {total_account['total_account_value']:,.2f}")
    
    print("\n📐 FÓRMULAS DE DEGIRO:")
    print(f"  • EUR (apalancamiento negativo) = Cuenta Completa - Cartera")
    print(f"    = {DEGIRO_DATA['cuenta_completa']:,.2f} - {DEGIRO_DATA['cartera']:,.2f}")
    print(f"    = {DEGIRO_DATA['eur']:,.2f} ✓")
    print(f"\n  • Cuenta Completa = Cartera + EUR")
    print(f"    = {DEGIRO_DATA['cartera']:,.2f} + ({DEGIRO_DATA['eur']:,.2f})")
    print(f"    = {DEGIRO_DATA['cartera']:,.2f} - {abs(DEGIRO_DATA['eur']):,.2f}")
    print(f"    = {DEGIRO_DATA['cuenta_completa']:,.2f} ✓")
    
    # 10. Intentar calcular "Cuenta Completa" como DeGiro con nuestros datos
    print("\n🔍 CÁLCULO 'Cuenta Completa' COMO DEGIRO (con nuestros datos):")
    app_cuenta_completa_degiro_style = APP_DATA['valor_total_cartera'] - abs(APP_DATA['dinero_prestado']) if APP_DATA['dinero_prestado'] > 0 else APP_DATA['valor_total_cartera']
    print(f"  • Cuenta Completa (DeGiro style) = Cartera - Apalancamiento")
    print(f"    = {APP_DATA['valor_total_cartera']:,.2f} - {abs(APP_DATA['dinero_prestado']):,.2f}")
    print(f"    = {app_cuenta_completa_degiro_style:,.2f}")
    print(f"  • DeGiro muestra:                € {DEGIRO_DATA['cuenta_completa']:>15,.2f}")
    print(f"  • Diferencia:                    € {app_cuenta_completa_degiro_style - DEGIRO_DATA['cuenta_completa']:>15,.2f}")
    
    # 11. ¿Qué representa "Cuenta Completa" en DeGiro?
    print("\n💡 INTERPRETACIÓN:")
    print("  DeGiro 'Cuenta Completa' parece ser el valor de la cartera SIN contar el apalancamiento.")
    print("  Es decir: Cuenta Completa = Cartera - Dinero Prestado")
    print("  Esto representaría el 'valor real' que el usuario tiene en la cuenta.")
    print("\n  En nuestra app calculamos:")
    print(f"  • Valor Real Cuenta = Dinero Usuario + P&L No Realizado = {total_account['total_account_value']:,.2f}")
    print(f"  • Cuenta Completa (estilo DeGiro) = Cartera - Apalancamiento = {app_cuenta_completa_degiro_style:,.2f}")
    
    print("\n" + "="*80 + "\n")

