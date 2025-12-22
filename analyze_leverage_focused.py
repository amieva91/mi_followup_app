"""
Análisis enfocado en el cálculo del APALANCAMIENTO
Comparando con los nuevos datos actualizados de DeGiro
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
    print(f"ANÁLISIS ENFOCADO: CÁLCULO DE APALANCAMIENTO")
    print(f"{'='*80}\n")
    
    # DATOS ACTUALIZADOS DE DEGIRO (de las nuevas capturas)
    DEGIRO = {
        'cuenta_completa': 70623.95,
        'cartera': 99882.46,
        'eur': -29258.51,  # Negativo = apalancamiento
        'margen_libre': 16011.11,
        'total_bp': 47170.31
    }
    
    # DATOS ACTUALIZADOS DE LA APP (de las nuevas capturas)
    APP_CAPTURE = {
        'valor_real_cuenta': 34286.03,
        'dinero_prestado': 48754.79,
        'coste_total': 83040.82,
        'dinero_usuario': -34286.03,  # ⚠️ NEGATIVO - esto parece incorrecto
        'valor_total_cartera': 97999.55,
        'pl_realizado': 31395.21,
        'pl_no_realizado': 14958.73,
        'dividendos': 12478.32,
        'comisiones': 12807.48,
        'depositos': 36718.98,
        'retiradas': 33499.00
    }
    
    print("📊 DATOS ACTUALIZADOS DE DEGIRO:")
    print(f"  • Cuenta Completa:      € {DEGIRO['cuenta_completa']:>15,.2f}")
    print(f"  • Cartera:              € {DEGIRO['cartera']:>15,.2f}")
    print(f"  • EUR (apalancamiento): € {DEGIRO['eur']:>15,.2f}")
    print(f"  • Margen libre:         € {DEGIRO['margen_libre']:>15,.2f}")
    print(f"  • Total B/P:            € {DEGIRO['total_bp']:>15,.2f}")
    
    print("\n💻 DATOS ACTUALIZADOS DE LA APP:")
    print(f"  • Valor Real Cuenta:    € {APP_CAPTURE['valor_real_cuenta']:>15,.2f}")
    print(f"  • Dinero Prestado:      € {APP_CAPTURE['dinero_prestado']:>15,.2f}")
    print(f"  • Coste Total:          € {APP_CAPTURE['coste_total']:>15,.2f}")
    print(f"  • Dinero Usuario:       € {APP_CAPTURE['dinero_usuario']:>15,.2f} ⚠️ NEGATIVO")
    print(f"  • Valor Total Cartera:  € {APP_CAPTURE['valor_total_cartera']:>15,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 1: VERIFICACIÓN DEL CÁLCULO ACTUAL")
    print("="*80)
    
    # Calcular "Dinero Usuario" manualmente según la fórmula
    dinero_usuario_manual = (
        APP_CAPTURE['depositos'] - 
        APP_CAPTURE['retiradas'] + 
        APP_CAPTURE['pl_realizado'] + 
        APP_CAPTURE['dividendos'] - 
        APP_CAPTURE['comisiones']
    )
    
    print("\n📋 Verificación del cálculo de 'Dinero Usuario':")
    print(f"  Fórmula: Depósitos - Retiradas + P&L Realizado + Dividendos - Comisiones")
    print(f"  = {APP_CAPTURE['depositos']:,.2f} - {APP_CAPTURE['retiradas']:,.2f} + {APP_CAPTURE['pl_realizado']:,.2f} + {APP_CAPTURE['dividendos']:,.2f} - {APP_CAPTURE['comisiones']:,.2f}")
    print(f"  = {dinero_usuario_manual:,.2f}")
    print(f"  App muestra: {APP_CAPTURE['dinero_usuario']:,.2f}")
    
    if dinero_usuario_manual != APP_CAPTURE['dinero_usuario']:
        print(f"  ⚠️  ¡DISCREPANCIA! El cálculo manual da {dinero_usuario_manual:,.2f} pero la app muestra {APP_CAPTURE['dinero_usuario']:,.2f}")
    else:
        print(f"  ✓ El cálculo coincide")
    
    # Verificar el cálculo de apalancamiento
    apalancamiento_calculado = APP_CAPTURE['coste_total'] - dinero_usuario_manual
    print(f"\n📋 Verificación del cálculo de 'Apalancamiento':")
    print(f"  Fórmula: Coste Total - Dinero Usuario")
    print(f"  = {APP_CAPTURE['coste_total']:,.2f} - {dinero_usuario_manual:,.2f}")
    print(f"  = {apalancamiento_calculado:,.2f}")
    print(f"  App muestra: {APP_CAPTURE['dinero_prestado']:,.2f}")
    print(f"  DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 2: COMPARACIÓN DIRECTA DEL APALANCAMIENTO")
    print("="*80)
    
    print(f"\n📊 Apalancamiento:")
    print(f"  • DeGiro:              € {abs(DEGIRO['eur']):>15,.2f}")
    print(f"  • App:                 € {APP_CAPTURE['dinero_prestado']:>15,.2f}")
    print(f"  • Diferencia:          € {APP_CAPTURE['dinero_prestado'] - abs(DEGIRO['eur']):>15,.2f}")
    print(f"  • Diferencia %:        {(APP_CAPTURE['dinero_prestado'] - abs(DEGIRO['eur'])) / abs(DEGIRO['eur']) * 100:>15,.2f}%")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 3: ¿QUÉ COMPONENTES PUEDEN ESTAR CAUSANDO LA DIFERENCIA?")
    print("="*80)
    
    # Obtener datos reales de la BD
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
    
    # Obtener métricas reales
    metrics = BasicMetrics.get_all_metrics(user_id, total_value, total_cost, total_pl)
    leverage_real = metrics['leverage']
    total_account_real = metrics['total_account']
    
    print("\n📊 Datos REALES calculados de la BD:")
    print(f"  • Valor Total Cartera:  € {total_value:>15,.2f}")
    print(f"  • Coste Total:          € {total_cost:>15,.2f}")
    print(f"  • Dinero Usuario:       € {leverage_real['user_money']:>15,.2f}")
    print(f"  • Apalancamiento:       € {leverage_real['broker_money']:>15,.2f}")
    
    print(f"\n📊 Componentes del Dinero Usuario (de BD):")
    print(f"  • Depósitos:            € {total_account_real['deposits']:>15,.2f}")
    print(f"  • Retiradas:            € {total_account_real['withdrawals']:>15,.2f}")
    print(f"  • P&L Realizado:        € {total_account_real['pl_realized']:>15,.2f}")
    print(f"  • Dividendos:           € {total_account_real['dividends']:>15,.2f}")
    print(f"  • Comisiones:           € {total_account_real['fees']:>15,.2f}")
    
    print("\n📊 Comparación BD vs Captura:")
    print(f"  • Coste Total:")
    print(f"    BD: {total_cost:,.2f} | Captura: {APP_CAPTURE['coste_total']:,.2f} | Diff: {total_cost - APP_CAPTURE['coste_total']:,.2f}")
    print(f"  • Dinero Usuario:")
    print(f"    BD: {leverage_real['user_money']:,.2f} | Captura: {APP_CAPTURE['dinero_usuario']:,.2f} | Diff: {leverage_real['user_money'] - APP_CAPTURE['dinero_usuario']:,.2f}")
    print(f"  • Apalancamiento:")
    print(f"    BD: {leverage_real['broker_money']:,.2f} | Captura: {APP_CAPTURE['dinero_prestado']:,.2f} | Diff: {leverage_real['broker_money'] - APP_CAPTURE['dinero_prestado']:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 4: PRUEBAS CON DIFERENTES FÓRMULAS PARA EXPLICAR DEGIRO")
    print("="*80)
    
    # Si DeGiro usa valor de mercado
    apalancamiento_valor_mercado = total_value - leverage_real['user_money']
    print(f"\n💡 Si DeGiro usa VALOR DE MERCADO:")
    print(f"   Apalancamiento = Valor Cartera - Dinero Usuario")
    print(f"   = {total_value:,.2f} - {leverage_real['user_money']:,.2f}")
    print(f"   = {apalancamiento_valor_mercado:,.2f}")
    print(f"   DeGiro muestra: {abs(DEGIRO['eur']):,.2f}")
    print(f"   Diferencia: {apalancamiento_valor_mercado - abs(DEGIRO['eur']):,.2f}")
    
    # Si DeGiro usa coste pero con diferente "Dinero Usuario"
    # ¿Qué "Dinero Usuario" necesitaríamos para obtener el apalancamiento de DeGiro?
    dinero_usuario_necesario_coste = total_cost - abs(DEGIRO['eur'])
    print(f"\n💡 Si DeGiro usa COSTE, ¿qué 'Dinero Usuario' necesitaría?")
    print(f"   Si: Apalancamiento = Coste - Dinero Usuario")
    print(f"   Entonces: Dinero Usuario = Coste - Apalancamiento")
    print(f"   = {total_cost:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"   = {dinero_usuario_necesario_coste:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage_real['user_money']:,.2f}")
    print(f"   Diferencia: {dinero_usuario_necesario_coste - leverage_real['user_money']:,.2f}")
    
    # ¿Qué "Dinero Usuario" necesitaríamos si usa valor de mercado?
    dinero_usuario_necesario_valor = total_value - abs(DEGIRO['eur'])
    print(f"\n💡 Si DeGiro usa VALOR, ¿qué 'Dinero Usuario' necesitaría?")
    print(f"   Si: Apalancamiento = Valor - Dinero Usuario")
    print(f"   Entonces: Dinero Usuario = Valor - Apalancamiento")
    print(f"   = {total_value:,.2f} - {abs(DEGIRO['eur']):,.2f}")
    print(f"   = {dinero_usuario_necesario_valor:,.2f}")
    print(f"   Nuestro Dinero Usuario: {leverage_real['user_money']:,.2f}")
    print(f"   Diferencia: {dinero_usuario_necesario_valor - leverage_real['user_money']:,.2f}")
    print(f"   DeGiro 'Cuenta Completa': {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   ¿Coincide con Cuenta Completa? {abs(dinero_usuario_necesario_valor - DEGIRO['cuenta_completa']) < 1.0}")
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS 5: VERIFICACIÓN DE TRANSACCIONES POR TIPO")
    print("="*80)
    
    # Verificar cada tipo de transacción
    deposits = Transaction.query.filter_by(user_id=user_id, transaction_type='DEPOSIT').all()
    withdrawals = Transaction.query.filter_by(user_id=user_id, transaction_type='WITHDRAWAL').all()
    dividends = Transaction.query.filter_by(user_id=user_id, transaction_type='DIVIDEND').all()
    fees = Transaction.query.filter_by(user_id=user_id).filter(
        Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
    ).all()
    
    total_deposits_bd = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits)
    total_withdrawals_bd = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals)
    total_dividends_bd = sum(convert_to_eur(abs(d.amount), d.currency) for d in dividends)
    total_fees_bd = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees)
    
    print(f"\n📊 Transacciones en BD:")
    print(f"  • Depósitos: {len(deposits):>4} transacciones = € {total_deposits_bd:>15,.2f}")
    print(f"  • Retiradas: {len(withdrawals):>4} transacciones = € {total_withdrawals_bd:>15,.2f}")
    print(f"  • Dividendos: {len(dividends):>4} transacciones = € {total_dividends_bd:>15,.2f}")
    print(f"  • Comisiones: {len(fees):>4} transacciones = € {total_fees_bd:>15,.2f}")
    
    print(f"\n📊 Comparación con captura:")
    print(f"  • Depósitos: BD={total_deposits_bd:,.2f} | Captura={APP_CAPTURE['depositos']:,.2f} | Diff={total_deposits_bd - APP_CAPTURE['depositos']:,.2f}")
    print(f"  • Retiradas: BD={total_withdrawals_bd:,.2f} | Captura={APP_CAPTURE['retiradas']:,.2f} | Diff={total_withdrawals_bd - APP_CAPTURE['retiradas']:,.2f}")
    print(f"  • Dividendos: BD={total_dividends_bd:,.2f} | Captura={APP_CAPTURE['dividendos']:,.2f} | Diff={total_dividends_bd - APP_CAPTURE['dividendos']:,.2f}")
    print(f"  • Comisiones: BD={total_fees_bd:,.2f} | Captura={APP_CAPTURE['comisiones']:,.2f} | Diff={total_fees_bd - APP_CAPTURE['comisiones']:,.2f}")
    
    print("\n" + "="*80)
    print("📝 PLAN DE INVESTIGACIÓN SUGERIDO")
    print("="*80)
    
    print("\n1. VERIFICAR el cálculo del 'Dinero Usuario':")
    print("   • ¿Por qué aparece negativo en la captura?")
    print("   • Verificar que la fórmula se esté aplicando correctamente")
    print("   • Comparar cada componente (depósitos, retiradas, etc.)")
    
    print("\n2. VERIFICAR el cálculo del 'Apalancamiento':")
    print("   • Fórmula actual: Coste Total - Dinero Usuario")
    print("   • ¿Es correcta esta fórmula?")
    print("   • ¿Debería usar valor de mercado en lugar de coste?")
    
    print("\n3. INVESTIGAR qué representa exactamente 'Cuenta Completa' de DeGiro:")
    print(f"   • DeGiro muestra: {DEGIRO['cuenta_completa']:,.2f}")
    print(f"   • Si calculamos: Cartera - Apalancamiento = {total_value:,.2f} - {abs(DEGIRO['eur']):,.2f} = {dinero_usuario_necesario_valor:,.2f}")
    print(f"   • ¿'Cuenta Completa' = 'Dinero Usuario' de DeGiro?")
    
    print("\n4. VERIFICAR diferencias en componentes:")
    print("   • Revisar si hay transacciones que no estamos contabilizando")
    print("   • Verificar conversiones de moneda")
    print("   • Revisar si P&L Realizado se calcula correctamente")
    
    print("\n5. COMPARAR con la fórmula de DeGiro:")
    print("   • Si DeGiro: Cuenta Completa = Cartera - Apalancamiento")
    print("   • Entonces: Apalancamiento = Cartera - Cuenta Completa")
    print(f"   • Con datos DeGiro: {DEGIRO['cartera']:,.2f} - {DEGIRO['cuenta_completa']:,.2f} = {DEGIRO['cartera'] - DEGIRO['cuenta_completa']:,.2f}")
    print(f"   • DeGiro muestra EUR: {abs(DEGIRO['eur']):,.2f}")
    
    print("\n" + "="*80 + "\n")

