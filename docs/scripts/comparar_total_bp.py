"""
Comparar Total B/P de DeGiro con P&L Total de la app
Ajustando por la ganancia de Abengoa que DeGiro aún contabiliza
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
    print(f"COMPARACIÓN: Total B/P DeGiro vs P&L Total App")
    print(f"{'='*80}\n")
    
    # Datos de DeGiro
    DEGIRO_TOTAL_BP = 47152.71
    ABENGOA_GP_DEGIRO = 1218.26  # Ganancia que DeGiro muestra para Abengoa
    
    print("📊 DATOS DE DEGIRO:")
    print(f"  • Total B/P: € {DEGIRO_TOTAL_BP:,.2f}")
    print(f"  • Abengoa G/P en DeGiro: € {ABENGOA_GP_DEGIRO:,.2f}")
    print(f"    (Esta ganancia no debería contarse porque Abengoa está bloqueada)")
    
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
    total_pl_data = metrics['total_pl']
    
    app_total_pl = total_pl_data['total_pl']
    
    print(f"\n📊 DATOS DE LA APP:")
    print(f"  • P&L Total: € {app_total_pl:,.2f}")
    print(f"    Componentes:")
    print(f"      - P&L Realizado: € {total_pl_data['pl_realized']:,.2f}")
    print(f"      - P&L No Realizado: € {total_pl_data['pl_unrealized']:,.2f}")
    print(f"      - Dividendos: € {total_pl_data['dividends']:,.2f}")
    print(f"      - Comisiones: € {total_pl_data['fees']:,.2f}")
    
    print(f"\n{'='*80}")
    print("🔍 COMPARACIÓN")
    print(f"{'='*80}\n")
    
    # Ajustar DeGiro restando la ganancia de Abengoa
    degiro_total_bp_ajustado = DEGIRO_TOTAL_BP - ABENGOA_GP_DEGIRO
    
    print("1. Comparación directa:")
    print(f"   • DeGiro Total B/P: € {DEGIRO_TOTAL_BP:,.2f}")
    print(f"   • App P&L Total: € {app_total_pl:,.2f}")
    print(f"   • Diferencia: € {app_total_pl - DEGIRO_TOTAL_BP:,.2f}")
    
    print(f"\n2. Comparación ajustada (restando ganancia de Abengoa):")
    print(f"   • DeGiro Total B/P (ajustado): € {degiro_total_bp_ajustado:,.2f}")
    print(f"     (Total B/P - Ganancia Abengoa = {DEGIRO_TOTAL_BP:,.2f} - {ABENGOA_GP_DEGIRO:,.2f})")
    print(f"   • App P&L Total: € {app_total_pl:,.2f}")
    print(f"   • Diferencia ajustada: € {app_total_pl - degiro_total_bp_ajustado:,.2f}")
    
    # Verificar qué representa el Total B/P de DeGiro
    print(f"\n{'='*80}")
    print("🔍 ANÁLISIS: ¿Qué representa el Total B/P de DeGiro?")
    print(f"{'='*80}\n")
    
    print("El 'Total B/P' de DeGiro probablemente incluye:")
    print("  • P&L Realizado (ganancias/pérdidas de posiciones cerradas)")
    print("  • P&L No Realizado (ganancias/pérdidas de posiciones abiertas)")
    print("  • Posiblemente dividendos y comisiones")
    print("\n  (Similar a nuestro P&L Total)")
    
    # Si el ajuste mejora la comparación
    diferencia_antes = abs(app_total_pl - DEGIRO_TOTAL_BP)
    diferencia_despues = abs(app_total_pl - degiro_total_bp_ajustado)
    
    print(f"\n{'='*80}")
    print("📊 RESULTADO")
    print(f"{'='*80}\n")
    
    if diferencia_despues < diferencia_antes:
        mejora = diferencia_antes - diferencia_despues
        print(f"✅ El ajuste MEJORA la comparación:")
        print(f"   • Diferencia antes del ajuste: € {diferencia_antes:,.2f}")
        print(f"   • Diferencia después del ajuste: € {diferencia_despues:,.2f}")
        print(f"   • Mejora: € {mejora:,.2f}")
    else:
        print(f"⚠️  El ajuste NO mejora significativamente la comparación:")
        print(f"   • Diferencia antes del ajuste: € {diferencia_antes:,.2f}")
        print(f"   • Diferencia después del ajuste: € {diferencia_despues:,.2f}")
    
    porcentaje_diferencia = (diferencia_despues / degiro_total_bp_ajustado * 100) if degiro_total_bp_ajustado != 0 else 0
    print(f"\n   Diferencia porcentual: {porcentaje_diferencia:.2f}%")
    
    if diferencia_despues < 1000:
        print(f"\n   ✓ ¡Muy cercano! La diferencia es menor al 2%")
    elif diferencia_despues < 5000:
        print(f"\n   ✓ Bastante cercano. Podría haber diferencias en:")
        print(f"     - Dividendos no contabilizados igual")
        print(f"     - Comisiones calculadas diferente")
        print(f"     - P&L Realizado con diferencias menores")
    else:
        print(f"\n   ⚠️  Hay una diferencia significativa que podría deberse a:")
        print(f"     - Diferencias en cómo se calcula el P&L Realizado")
        print(f"     - Dividendos o comisiones no contabilizados igual")
        print(f"     - Otros componentes que DeGiro incluye/excluye")
    
    print("\n" + "="*80 + "\n")

