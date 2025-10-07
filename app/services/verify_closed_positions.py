"""
Verifica qué posiciones deberían estar cerradas (vendidas completamente)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Asset, Transaction, PortfolioHolding, BrokerAccount


def verify_closed_positions():
    """Verifica posiciones que deberían estar cerradas"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 80)
        print("VERIFICACIÓN DE POSICIONES CERRADAS")
        print("=" * 80)
        
        # Buscar cuenta DeGiro
        account = BrokerAccount.query.filter_by(account_name='Degiro').first()
        if not account:
            print("❌ Cuenta DeGiro no encontrada")
            return
        
        # Holdings actuales
        holdings = PortfolioHolding.query.filter_by(account_id=account.id).filter(
            PortfolioHolding.quantity > 0
        ).all()
        
        print(f"\n📊 Total holdings: {len(holdings)}")
        print(f"\n🔍 Verificando balance real de cada holding...\n")
        
        errors = []
        
        for h in holdings:
            # Calcular balance real desde transacciones
            txs = Transaction.query.filter_by(
                account_id=account.id,
                asset_id=h.asset_id
            ).all()
            
            total_bought = sum(tx.quantity for tx in txs if tx.transaction_type == 'BUY')
            total_sold = sum(tx.quantity for tx in txs if tx.transaction_type == 'SELL')
            real_balance = total_bought - total_sold
            
            # Comparar con el holding
            if abs(real_balance - h.quantity) > 0.01:  # Tolerancia de redondeo
                errors.append({
                    'symbol': h.asset.symbol,
                    'holding_qty': h.quantity,
                    'real_balance': real_balance,
                    'bought': total_bought,
                    'sold': total_sold
                })
            
            # Si el balance real es 0 o negativo, es un error
            if real_balance <= 0:
                print(f"❌ {h.asset.symbol:40s} | Holding: {h.quantity:8.0f} | Real: {real_balance:8.0f} | Comprado: {total_bought:8.0f} | Vendido: {total_sold:8.0f}")
        
        if errors:
            print(f"\n⚠️  Encontrados {len(errors)} holdings con errores de cálculo")
        else:
            print("\n✅ Todos los holdings tienen el balance correcto")


if __name__ == '__main__':
    verify_closed_positions()

