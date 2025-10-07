"""
Debug específico para un asset problemático
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Asset, Transaction, PortfolioHolding, BrokerAccount
from sqlalchemy import func


def debug_asset(symbol_name):
    """Debug de un asset específico"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 80)
        print(f"DEBUG: {symbol_name}")
        print("=" * 80)
        
        # Buscar asset
        asset = Asset.query.filter(Asset.symbol.like(f'%{symbol_name}%')).first()
        if not asset:
            print(f"❌ Asset '{symbol_name}' no encontrado")
            return
        
        print(f"\n📊 Asset: {asset.symbol} ({asset.name})")
        print(f"   ISIN: {asset.isin}")
        print(f"   Currency: {asset.currency}")
        
        # Holdings de este asset
        holdings = PortfolioHolding.query.filter_by(asset_id=asset.id).all()
        print(f"\n🏦 Holdings: {len(holdings)}")
        for h in holdings:
            print(f"   - Cuenta: {h.account.broker.name} - {h.account.account_name}")
            print(f"     Cantidad: {h.quantity}")
            print(f"     Precio medio: {h.average_buy_price:.2f}")
            print(f"     Coste total: {h.total_cost:.2f}")
        
        # Transacciones de este asset
        txs = Transaction.query.filter_by(asset_id=asset.id).order_by(Transaction.transaction_date).all()
        print(f"\n📝 Transacciones: {len(txs)}")
        
        buy_count = sum(1 for tx in txs if tx.transaction_type == 'BUY')
        sell_count = sum(1 for tx in txs if tx.transaction_type == 'SELL')
        
        print(f"   - Compras: {buy_count}")
        print(f"   - Ventas: {sell_count}")
        
        # Calcular balance
        total_bought = sum(tx.quantity for tx in txs if tx.transaction_type == 'BUY')
        total_sold = sum(tx.quantity for tx in txs if tx.transaction_type == 'SELL')
        balance = total_bought - total_sold
        
        print(f"\n💰 Balance calculado:")
        print(f"   - Total comprado: {total_bought}")
        print(f"   - Total vendido: {total_sold}")
        print(f"   - Balance final: {balance}")
        
        if balance <= 0:
            print(f"\n⚠️  ¡Este holding debería ser eliminado! (balance={balance})")
        
        # Mostrar últimas 5 transacciones
        print(f"\n📋 Últimas 5 transacciones:")
        for tx in txs[-5:]:
            print(f"   - {tx.transaction_date.date()}: {tx.transaction_type} {tx.quantity} @ {tx.price:.2f}")


if __name__ == '__main__':
    # Debug VARTA AG (tiene 36 transacciones)
    debug_asset('VARTA')
    
    print("\n" + "=" * 80 + "\n")
    
    # Debug ALPHABET (debería tener posición)
    debug_asset('ALPHABET')

