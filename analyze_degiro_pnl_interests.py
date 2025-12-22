"""
Análisis del Total B/P de DeGiro y verificación de componentes
Incluye verificación de intereses y comisiones
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
    print(f"ANÁLISIS: Total B/P de DeGiro y Componentes")
    print(f"{'='*80}\n")
    
    # Datos de DeGiro
    DEGIRO = {
        'cuenta_completa': 69519.94,
        'cartera': 93748.23,
        'eur': -24228.29,
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
    total_pl_data = metrics['total_pl']
    
    print("📊 DATOS DE DEGIRO:")
    print(f"  • Cuenta Completa:      € {DEGIRO['cuenta_completa']:>15,.2f}")
    print(f"  • Cartera:              € {DEGIRO['cartera']:>15,.2f}")
    print(f"  • EUR (saldo cash):     € {DEGIRO['eur']:>15,.2f}")
    print(f"  • Margen libre:         € {DEGIRO['margen_libre']:>15,.2f}")
    print(f"  • Total B/P:            € {DEGIRO['total_bp']:>15,.2f}")
    
    print("\n💻 NUESTRO P&L TOTAL:")
    print(f"  • P&L Total:            € {total_pl_data['total_pl']:>15,.2f}")
    print(f"  • P&L Realizado:        € {total_pl_data['pl_realized']:>15,.2f}")
    print(f"  • P&L No Realizado:     € {total_pl_data['pl_unrealized']:>15,.2f}")
    print(f"  • Dividendos:           € {total_pl_data['dividends']:>15,.2f}")
    print(f"  • Comisiones:           € {total_pl_data['fees']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 1: COMPONENTES DEL P&L TOTAL")
    print("="*80)
    
    print("\n📋 Componentes de nuestro P&L Total:")
    print(f"  • P&L Realizado:        € {total_pl_data['pl_realized']:>15,.2f}")
    print(f"  • P&L No Realizado:     € {total_pl_data['pl_unrealized']:>15,.2f}")
    print(f"  • Dividendos:           € {total_pl_data['dividends']:>15,.2f}")
    print(f"  • Comisiones:           € {total_pl_data['fees']:>15,.2f}")
    print(f"  ────────────────────────────────────────")
    print(f"  • P&L Total (nuestra fórmula):")
    print(f"    = Realizado + No Realizado + Dividendos - Comisiones")
    print(f"    = {total_pl_data['pl_realized']:,.2f} + {total_pl_data['pl_unrealized']:,.2f} + {total_pl_data['dividends']:,.2f} - {total_pl_data['fees']:,.2f}")
    calculated_pl = total_pl_data['pl_realized'] + total_pl_data['pl_unrealized'] + total_pl_data['dividends'] - total_pl_data['fees']
    print(f"    = {calculated_pl:,.2f}")
    print(f"  • DeGiro Total B/P:     € {DEGIRO['total_bp']:>15,.2f}")
    print(f"  • Diferencia:           € {calculated_pl - DEGIRO['total_bp']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 2: ¿INCLUYE DEGIRO INTERESES EN EL TOTAL B/P?")
    print("="*80)
    
    # Buscar transacciones de interés
    interest_transactions = Transaction.query.filter_by(
        user_id=user_id,
        transaction_type='INTEREST'
    ).all()
    
    total_interest = sum(convert_to_eur(abs(t.amount), t.currency) for t in interest_transactions)
    
    print(f"\n📊 Transacciones de INTERÉS en nuestra BD:")
    print(f"  • Total intereses:      € {total_interest:>15,.2f}")
    print(f"  • Número de transacciones: {len(interest_transactions)}")
    
    if interest_transactions:
        print(f"\n  Detalles de intereses (primeras 10):")
        for t in interest_transactions[:10]:
            print(f"    • {t.transaction_date.strftime('%Y-%m-%d')}: {t.amount:,.2f} {t.currency}")
    
    print(f"\n💡 Si DeGiro incluye intereses en Total B/P:")
    pl_with_interest = calculated_pl + total_interest
    print(f"  • Nuestro P&L Total + Intereses = {calculated_pl:,.2f} + {total_interest:,.2f}")
    print(f"    = {pl_with_interest:,.2f}")
    print(f"  • DeGiro Total B/P:     € {DEGIRO['total_bp']:>15,.2f}")
    print(f"  • Diferencia:           € {pl_with_interest - DEGIRO['total_bp']:>15,.2f}")
    
    print(f"\n💡 Si DeGiro NO incluye intereses:")
    print(f"  • Nuestro P&L Total:    € {calculated_pl:>15,.2f}")
    print(f"  • DeGiro Total B/P:     € {DEGIRO['total_bp']:>15,.2f}")
    print(f"  • Diferencia:           € {calculated_pl - DEGIRO['total_bp']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 3: ¿LAS COMISIONES YA ESTÁN INCLUIDAS?")
    print("="*80)
    
    print(f"\n📊 Nuestro cálculo de P&L Total:")
    print(f"  • P&L Realizado:        € {total_pl_data['pl_realized']:>15,.2f} (ya incluye comisiones de ventas)")
    print(f"  • Comisiones totales:   € {total_pl_data['fees']:>15,.2f} (restamos del total)")
    print(f"  • P&L Total = Realizado + No Realizado + Dividendos - Comisiones")
    
    print(f"\n💡 Si DeGiro YA incluye comisiones en el P&L Realizado:")
    pl_without_separate_fees = total_pl_data['pl_realized'] + total_pl_data['pl_unrealized'] + total_pl_data['dividends']
    print(f"  • P&L Total (sin restar comisiones): {pl_without_separate_fees:,.2f}")
    print(f"  • DeGiro Total B/P:     € {DEGIRO['total_bp']:>15,.2f}")
    print(f"  • Diferencia:           € {pl_without_separate_fees - DEGIRO['total_bp']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 4: VERIFICACIÓN DE TRANSACCIONES POR TIPO")
    print("="*80)
    
    # Contar transacciones por tipo
    transaction_counts = {}
    transaction_totals = {}
    
    types_to_check = ['DEPOSIT', 'WITHDRAWAL', 'DIVIDEND', 'FEE', 'COMMISSION', 'INTEREST', 'BUY', 'SELL']
    
    for txn_type in types_to_check:
        if txn_type in ['FEE', 'COMMISSION']:
            txns = Transaction.query.filter_by(user_id=user_id).filter(
                Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
            ).all()
            key = 'FEE/COMMISSION'
        else:
            txns = Transaction.query.filter_by(
                user_id=user_id,
                transaction_type=txn_type
            ).all()
            key = txn_type
        
        if key not in transaction_counts:
            transaction_counts[key] = 0
            transaction_totals[key] = 0.0
        
        transaction_counts[key] = len(txns)
        transaction_totals[key] = sum(convert_to_eur(abs(t.amount), t.currency) for t in txns)
    
    print(f"\n📊 Resumen de transacciones:")
    print(f"{'Tipo':<20} {'Cantidad':>10} {'Total EUR':>20}")
    print("-" * 50)
    for txn_type in ['DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'FEE/COMMISSION', 'INTEREST']:
        if txn_type in transaction_counts:
            count = transaction_counts[txn_type]
            total = transaction_totals[txn_type]
            print(f"{txn_type:<20} {count:>10} € {total:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 5: HIPÓTESIS SOBRE EL CÁLCULO DEL APALANCAMIENTO")
    print("="*80)
    
    print("\n💡 HIPÓTESIS A: DeGiro usa VALOR DE MERCADO para calcular apalancamiento")
    print(f"   Si: Apalancamiento = Valor Cartera - Dinero Usuario")
    print(f"   Entonces: Dinero Usuario = Valor Cartera - Apalancamiento")
    print(f"   Con datos DeGiro:")
    print(f"     Dinero Usuario = {DEGIRO['cartera']:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    dinero_usuario_hipotesis_a = DEGIRO['cartera'] - abs(DEGIRO['eur'])
    print(f"     = {dinero_usuario_hipotesis_a:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {dinero_usuario_hipotesis_a - leverage['user_money']:,.2f}")
    
    if abs(dinero_usuario_hipotesis_a - DEGIRO['cuenta_completa']) < 1.0:
        print(f"   ✓ ¡Coincide con 'Cuenta Completa' de DeGiro! ({DEGIRO['cuenta_completa']:,.2f})")
        print(f"   Esto sugiere que 'Cuenta Completa' = Dinero Usuario calculado con valor de mercado")
    
    print("\n💡 HIPÓTESIS B: DeGiro usa COSTE para calcular apalancamiento (como nosotros)")
    print(f"   Si: Apalancamiento = Coste Total - Dinero Usuario")
    print(f"   Entonces: Dinero Usuario = Coste Total - Apalancamiento")
    print(f"   Con datos DeGiro y nuestro coste:")
    print(f"     Dinero Usuario = {total_cost:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    dinero_usuario_hipotesis_b = total_cost - abs(DEGIRO['eur'])
    print(f"     = {dinero_usuario_hipotesis_b:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {dinero_usuario_hipotesis_b - leverage['user_money']:,.2f}")
    
    print("\n💡 HIPÓTESIS C: ¿Qué componentes incluye DeGiro en 'Dinero Usuario'?")
    print(f"   Si 'Cuenta Completa' = Dinero Usuario de DeGiro = {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   Nuestro Dinero Usuario = {leverage['user_money']:,.2f}")
    print(f"   Diferencia: {DEGIRO['cuenta_completa'] - leverage['user_money']:,.2f}")
    
    print(f"\n   Componentes de nuestro Dinero Usuario:")
    print(f"     • Depósitos:         € {total_account['deposits']:>15,.2f}")
    print(f"     • Retiradas:         € {total_account['withdrawals']:>15,.2f}")
    print(f"     • P&L Realizado:     € {total_account['pl_realized']:>15,.2f}")
    print(f"     • Dividendos:        € {total_account['dividends']:>15,.2f}")
    print(f"     • Comisiones:        € {total_account['fees']:>15,.2f}")
    print(f"     ────────────────────────────────────────")
    print(f"     • Total:             € {leverage['user_money']:>15,.2f}")
    
    print(f"\n   ¿Qué habría que añadir para llegar a {DEGIRO['cuenta_completa']:,.2f}?")
    diferencia = DEGIRO['cuenta_completa'] - leverage['user_money']
    print(f"     Diferencia necesaria: € {diferencia:,.2f}")
    
    # Probar diferentes combinaciones
    print(f"\n   Posibles componentes adicionales:")
    print(f"     • Si añadimos P&L No Realizado: {leverage['user_money'] + total_account['pl_unrealized']:,.2f}")
    print(f"       (pero ya dijimos que NO se incluye porque fluctúa)")
    print(f"     • Si añadimos Intereses: {leverage['user_money'] + total_interest:,.2f}")
    print(f"     • Si añadimos ambos: {leverage['user_money'] + total_account['pl_unrealized'] + total_interest:,.2f}")
    
    # ¿Podría ser que DeGiro calcule diferente?
    print(f"\n   ¿Y si DeGiro calcula Dinero Usuario como valor actual menos apalancamiento?")
    print(f"     = Valor Cartera - Apalancamiento")
    print(f"     = {total_value:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    dinero_usuario_valor_actual = total_value - abs(DEGIRO['eur'])
    print(f"     = {dinero_usuario_valor_actual:,.2f}")
    print(f"     DeGiro Cuenta Completa: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"     Diferencia: {dinero_usuario_valor_actual - DEGIRO['cuenta_completa']:,.2f}")
    
    print("\n" + "="*80)
    print("📝 CONCLUSIONES")
    print("="*80)
    
    print("\n1. Análisis del Total B/P:")
    print(f"   • DeGiro Total B/P: {DEGIRO['total_bp']:,.2f}")
    print(f"   • Nuestro P&L Total: {calculated_pl:,.2f}")
    print(f"   • Diferencia: {calculated_pl - DEGIRO['total_bp']:,.2f}")
    if total_interest > 0:
        print(f"   • Si incluimos intereses: {pl_with_interest:,.2f}")
        print(f"   • Diferencia con intereses: {pl_with_interest - DEGIRO['total_bp']:,.2f}")
    
    print("\n2. Análisis del Apalancamiento:")
    print(f"   • DeGiro EUR (apalancamiento): {abs(DEGIRO['eur']):,.2f}")
    print(f"   • Nuestro apalancamiento: {leverage['broker_money']:,.2f}")
    print(f"   • Diferencia: {abs(DEGIRO['eur']) - leverage['broker_money']:,.2f}")
    
    print("\n3. Hipótesis más probable:")
    if abs(dinero_usuario_hipotesis_a - DEGIRO['cuenta_completa']) < 1.0:
        print(f"   ✓ DeGiro usa VALOR DE MERCADO para calcular el apalancamiento")
        print(f"     'Cuenta Completa' = Dinero Usuario = Cartera - Apalancamiento")
        print(f"     Esto explicaría por qué 'Cuenta Completa' coincide con el cálculo")
    
    print("\n" + "="*80 + "\n")

