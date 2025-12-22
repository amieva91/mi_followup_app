"""
Investigación profunda componente por componente
Comparar cada elemento del cálculo de "Dinero Usuario"
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User, Transaction
from app.services.metrics.basic_metrics import BasicMetrics
from app.models.portfolio import PortfolioHolding
from app.services.currency_service import convert_to_eur
from decimal import Decimal

app = create_app()

with app.app_context():
    user = User.query.first()
    if not user:
        print("No hay usuarios")
        sys.exit(1)
    
    user_id = user.id
    
    print(f"\n{'='*80}")
    print(f"INVESTIGACIÓN PROFUNDA: Comparación Componente por Componente")
    print(f"{'='*80}\n")
    
    # Datos DeGiro
    DEGIRO_APALANCAMIENTO = 29258.51
    DEGIRO_CARTERA = 99882.46
    DEGIRO_CUENTA_COMPLETA = 70623.95
    
    # Calcular valores
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
    
    print("📊 SITUACIÓN ACTUAL:")
    print(f"  • Apalancamiento App:      € {leverage['broker_money']:>15,.2f}")
    print(f"  • Apalancamiento DeGiro:   € {DEGIRO_APALANCAMIENTO:>15,.2f}")
    print(f"  • Diferencia:              € {leverage['broker_money'] - DEGIRO_APALANCAMIENTO:>15,.2f}")
    
    print(f"\n  • Dinero Usuario App:      € {leverage['user_money']:>15,.2f}")
    
    # Si DeGiro usa coste, necesitaría este Dinero Usuario
    dinero_usuario_necesario_coste = total_cost - DEGIRO_APALANCAMIENTO
    print(f"  • Dinero Usuario necesario (si DeGiro usa coste): € {dinero_usuario_necesario_coste:>15,.2f}")
    print(f"  • Diferencia necesaria:    € {dinero_usuario_necesario_coste - leverage['user_money']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 1: DESGLOSE DETALLADO DE COMPONENTES")
    print("="*80)
    
    # Obtener todas las transacciones y analizarlas
    deposits = Transaction.query.filter_by(user_id=user_id, transaction_type='DEPOSIT').all()
    withdrawals = Transaction.query.filter_by(user_id=user_id, transaction_type='WITHDRAWAL').all()
    dividends = Transaction.query.filter_by(user_id=user_id, transaction_type='DIVIDEND').all()
    fees = Transaction.query.filter_by(user_id=user_id).filter(
        Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
    ).all()
    
    total_deposits = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits)
    total_withdrawals = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals)
    total_dividends = sum(convert_to_eur(abs(d.amount), d.currency) for d in dividends)
    total_fees = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees)
    
    print(f"\n📋 Componentes actuales:")
    print(f"  • Depósitos:              € {total_deposits:>15,.2f} ({len(deposits)} transacciones)")
    print(f"  • Retiradas:              € {total_withdrawals:>15,.2f} ({len(withdrawals)} transacciones)")
    print(f"  • P&L Realizado:          € {total_account['pl_realized']:>15,.2f}")
    print(f"  • Dividendos:             € {total_dividends:>15,.2f} ({len(dividends)} transacciones)")
    print(f"  • Comisiones:             € {total_fees:>15,.2f} ({len(fees)} transacciones)")
    print(f"  ────────────────────────────────────────")
    print(f"  • Total Dinero Usuario:   € {leverage['user_money']:>15,.2f}")
    
    diferencia_necesaria = dinero_usuario_necesario_coste - leverage['user_money']
    print(f"\n💡 Para igualar a DeGiro necesitamos añadir: € {diferencia_necesaria:,.2f}")
    print(f"   Esto representa un {(diferencia_necesaria / leverage['user_money'] * 100):,.2f}% del Dinero Usuario actual")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 2: ¿QUÉ PODRÍA REPRESENTAR ESA DIFERENCIA?")
    print("="*80)
    
    print(f"\n💡 HIPÓTESIS A: ¿Es parte del P&L No Realizado?")
    print(f"   P&L No Realizado: {total_account['pl_unrealized']:,.2f}")
    print(f"   Diferencia necesaria: {diferencia_necesaria:,.2f}")
    print(f"   Relación: {diferencia_necesaria / total_account['pl_unrealized'] * 100:.2f}% del P&L No Realizado")
    
    print(f"\n💡 HIPÓTESIS B: ¿Es alguna parte de las comisiones que no estamos restando?")
    print(f"   Comisiones totales: {total_fees:,.2f}")
    print(f"   Diferencia necesaria: {diferencia_necesaria:,.2f}")
    if diferencia_necesaria < total_fees:
        print(f"   ¿DeGiro resta menos comisiones? (diferencia = {(1 - diferencia_necesaria/total_fees)*100:.2f}% de las comisiones)")
    
    print(f"\n💡 HIPÓTESIS C: ¿Hay alguna diferencia en el cálculo del P&L Realizado?")
    print(f"   P&L Realizado actual: {total_account['pl_realized']:,.2f}")
    print(f"   Si añadimos la diferencia: {total_account['pl_realized'] + diferencia_necesaria:,.2f}")
    print(f"   Incremento: {(diferencia_necesaria / total_account['pl_realized'] * 100):,.2f}%")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 3: VERIFICAR SI HAY COMISIONES INCLUIDAS EN EL P&L REALIZADO")
    print("="*80)
    
    # Revisar si las comisiones de ventas están siendo restadas correctamente
    print("\n📊 Análisis del P&L Realizado:")
    print("   El P&L Realizado se calcula como: Ingresos venta (después de comisiones) - Coste FIFO")
    print("   Las comisiones de venta ya están restadas en el cálculo del P&L Realizado")
    print("   Pero luego restamos las comisiones totales del 'Dinero Usuario'")
    print("\n   ¿Podría haber doble resta de comisiones de ventas?")
    
    # Buscar comisiones de ventas específicamente
    sells = Transaction.query.filter_by(user_id=user_id, transaction_type='SELL').all()
    total_commission_sells = 0.0
    total_fees_sells = 0.0
    for sell in sells:
        if sell.commission:
            total_commission_sells += convert_to_eur(sell.commission, sell.currency)
        if sell.fees:
            total_fees_sells += convert_to_eur(sell.fees, sell.currency)
    
    comisiones_ventas = total_commission_sells + total_fees_sells
    
    print(f"\n   Comisiones/Fees de ventas (SELL): € {comisiones_ventas:,.2f}")
    print(f"   Comisiones totales (FEE/COMMISSION): € {total_fees:,.2f}")
    print(f"   Diferencia: € {abs(comisiones_ventas - total_fees):,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 4: VERIFICAR SI DEGIRO CALCULA DIFERENTE EL COSTE")
    print("="*80)
    
    # ¿Podría ser que DeGiro use un coste diferente?
    # Si usamos valor de mercado con el apalancamiento de DeGiro
    coste_implicito_degiro = DEGIRO_APALANCAMIENTO + leverage['user_money']
    print(f"\n💡 Si usamos nuestro Dinero Usuario y el apalancamiento de DeGiro:")
    print(f"   Coste implícito = Apalancamiento + Dinero Usuario")
    print(f"   = {DEGIRO_APALANCAMIENTO:,.2f} + {leverage['user_money']:,.2f}")
    print(f"   = {coste_implicito_degiro:,.2f}")
    print(f"   Nuestro Coste Total: {total_cost:,.2f}")
    print(f"   Diferencia: {coste_implicito_degiro - total_cost:,.2f}")
    
    # ¿O si usamos el valor de mercado?
    valor_implicito_degiro = DEGIRO_APALANCAMIENTO + dinero_usuario_necesario_coste
    print(f"\n💡 Si usamos el Dinero Usuario necesario y el apalancamiento de DeGiro:")
    print(f"   Valor/Coste implícito = Apalancamiento + Dinero Usuario necesario")
    print(f"   = {DEGIRO_APALANCAMIENTO:,.2f} + {dinero_usuario_necesario_coste:,.2f}")
    print(f"   = {valor_implicito_degiro:,.2f}")
    print(f"   Nuestro Coste Total: {total_cost:,.2f}")
    print(f"   Nuestro Valor Total: {total_value:,.2f}")
    print(f"   Diferencia con coste: {valor_implicito_degiro - total_cost:,.2f}")
    print(f"   Diferencia con valor: {valor_implicito_degiro - total_value:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 5: ¿QUÉ PASARÍA SI...?")
    print("="*80)
    
    print("\n💡 ESCENARIO A: Si NO restáramos las comisiones del Dinero Usuario:")
    dinero_sin_restar_comisiones = total_deposits - total_withdrawals + total_account['pl_realized'] + total_dividends
    print(f"   Dinero Usuario = Depósitos - Retiradas + P&L Realizado + Dividendos")
    print(f"   = {dinero_sin_restar_comisiones:,.2f}")
    print(f"   Diferencia con necesario: {dinero_sin_restar_comisiones - dinero_usuario_necesario_coste:,.2f}")
    
    print("\n💡 ESCENARIO B: Si añadimos P&L No Realizado:")
    dinero_con_unrealized = leverage['user_money'] + total_account['pl_unrealized']
    print(f"   Dinero Usuario + P&L No Realizado = {dinero_con_unrealized:,.2f}")
    print(f"   Diferencia con necesario: {dinero_con_unrealized - dinero_usuario_necesario_coste:,.2f}")
    
    print("\n💡 ESCENARIO C: Si NO restáramos comisiones Y añadimos P&L No Realizado:")
    dinero_escenario_c = dinero_sin_restar_comisiones + total_account['pl_unrealized']
    print(f"   = {dinero_escenario_c:,.2f}")
    print(f"   Diferencia con necesario: {dinero_escenario_c - dinero_usuario_necesario_coste:,.2f}")
    
    print("\n💡 ESCENARIO D: Si añadimos la mitad de las comisiones (¿comisiones de compras vs ventas?):")
    dinero_mitad_comisiones = leverage['user_money'] + (total_fees / 2)
    print(f"   Dinero Usuario + (Comisiones / 2) = {dinero_mitad_comisiones:,.2f}")
    print(f"   Diferencia con necesario: {dinero_mitad_comisiones - dinero_usuario_necesario_coste:,.2f}")
    
    print("\n" + "="*80)
    print("📝 CONCLUSIÓN Y RECOMENDACIONES")
    print("="*80)
    
    print("\n1. Diferencia clave:")
    print(f"   Necesitamos añadir € {diferencia_necesaria:,.2f} al Dinero Usuario")
    print(f"   para igualar el cálculo de DeGiro (si usa coste)")
    
    print("\n2. Posibles explicaciones:")
    if abs(diferencia_necesaria - total_account['pl_unrealized']) < 5000:
        print(f"   • Podría estar relacionado con P&L No Realizado ({total_account['pl_unrealized']:,.2f})")
    if abs(diferencia_necesaria - (total_fees / 2)) < 5000:
        print(f"   • Podría ser mitad de comisiones ({total_fees / 2:,.2f})")
    if abs(dinero_sin_restar_comisiones - dinero_usuario_necesario_coste) < 5000:
        print(f"   • DeGiro podría NO estar restando comisiones del Dinero Usuario")
    
    print("\n3. Próximos pasos:")
    print("   • Revisar documentación de DeGiro sobre cómo calculan 'Cuenta Completa'")
    print("   • Comparar transacción por transacción el P&L Realizado")
    print("   • Verificar si DeGiro incluye/excluye algún componente específico")
    print("   • Contactar con DeGiro para aclarar su metodología")
    
    print("\n" + "="*80 + "\n")

