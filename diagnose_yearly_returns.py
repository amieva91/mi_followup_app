#!/usr/bin/env python3
"""
Script de diagnóstico para comparar rentabilidades año a año entre entornos
"""
import sys
from datetime import datetime
from app import create_app, db
from app.models import Transaction
from app.services.metrics.modified_dietz import ModifiedDietzCalculator

def diagnose_yearly_returns(user_id, env_name):
    """Diagnostica las rentabilidades año a año para un usuario"""
    print(f"\n{'='*60}")
    print(f"DIAGNÓSTICO: {env_name.upper()}")
    print(f"{'='*60}")
    
    # Obtener primera transacción
    first_txn = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.transaction_date).first()
    if not first_txn:
        print("❌ No hay transacciones")
        return
    
    print(f"\n📅 Primera transacción: {first_txn.transaction_date}")
    print(f"📅 Fecha actual del sistema: {datetime.now()}")
    
    # Obtener rentabilidades año a año
    yearly_returns = ModifiedDietzCalculator.get_yearly_returns(user_id)
    
    print(f"\n📊 Rentabilidades Año a Año:")
    print(f"{'Año':<8} {'Return %':<12} {'Ganancia EUR':<15} {'VI':<12} {'VF':<12} {'CF':<12} {'Días':<6}")
    print("-" * 80)
    
    for yr in yearly_returns:
        # Obtener detalles del cálculo
        result = ModifiedDietzCalculator.calculate_return(
            user_id, yr['start_date'], yr['end_date']
        )
        
        print(f"{yr['year']}{'(YTD)' if yr['is_ytd'] else '':<8} "
              f"{yr['return_pct']:>10.2f}%  "
              f"{yr['absolute_gain']:>13.2f}  "
              f"{result['start_value']:>10.2f}  "
              f"{result['end_value']:>10.2f}  "
              f"{result['cash_flows']:>10.2f}  "
              f"{result['days']:>5}")
    
    # Contar transacciones por tipo
    print(f"\n📈 Resumen de Transacciones:")
    for txn_type in ['DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'FEE']:
        count = Transaction.query.filter_by(user_id=user_id, transaction_type=txn_type).count()
        if count > 0:
            print(f"  {txn_type}: {count}")
    
    # Verificar fechas de transacciones
    print(f"\n📅 Rango de fechas de transacciones:")
    first = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.transaction_date.asc()).first()
    last = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.transaction_date.desc()).first()
    if first and last:
        print(f"  Primera: {first.transaction_date}")
        print(f"  Última: {last.transaction_date}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python diagnose_yearly_returns.py <environment> [user_id]")
        print("  environment: 'development' o 'production'")
        print("  user_id: ID del usuario (opcional, por defecto 1)")
        sys.exit(1)
    
    env = sys.argv[1]
    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    app = create_app(env)
    with app.app_context():
        diagnose_yearly_returns(user_id, env)

