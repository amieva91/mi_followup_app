"""
Script de diagnóstico para ver qué holdings existen en la BD
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import PortfolioHolding, Transaction, Asset, BrokerAccount


def diagnose():
    """Diagnostica los holdings"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 80)
        print("DIAGNÓSTICO DE HOLDINGS")
        print("=" * 80)
        
        # Total de holdings
        total_holdings = PortfolioHolding.query.count()
        print(f"\n📊 Total holdings en BD: {total_holdings}")
        
        # Holdings con quantity > 0
        active_holdings = PortfolioHolding.query.filter(PortfolioHolding.quantity > 0).count()
        print(f"✅ Holdings activos (qty > 0): {active_holdings}")
        
        # Holdings con quantity = 0
        zero_holdings = PortfolioHolding.query.filter(PortfolioHolding.quantity == 0).count()
        print(f"⚠️  Holdings con quantity = 0: {zero_holdings}")
        
        # Holdings con quantity < 0
        negative_holdings = PortfolioHolding.query.filter(PortfolioHolding.quantity < 0).count()
        print(f"❌ Holdings con quantity < 0: {negative_holdings}")
        
        # Por cuenta
        print("\n📋 Holdings por cuenta:")
        accounts = BrokerAccount.query.all()
        for account in accounts:
            holdings_count = PortfolioHolding.query.filter_by(account_id=account.id).filter(PortfolioHolding.quantity > 0).count()
            print(f"   {account.broker.name} - {account.account_name}: {holdings_count} holdings")
        
        # Holdings problemáticos
        print("\n⚠️  Holdings con cantidades muy altas:")
        high_qty_holdings = PortfolioHolding.query.filter(PortfolioHolding.quantity > 100000).all()
        for h in high_qty_holdings:
            print(f"   - {h.asset.symbol}: {h.quantity:,.0f} @ {h.average_buy_price:.2f} {h.asset.currency}")
            print(f"     Cuenta: {h.account.broker.name} - {h.account.account_name}")
        
        # Holdings duplicados (mismo asset en misma cuenta)
        print("\n🔍 Verificando duplicados...")
        from sqlalchemy import func
        duplicates = db.session.query(
            PortfolioHolding.account_id,
            PortfolioHolding.asset_id,
            func.count(PortfolioHolding.id).label('count')
        ).group_by(
            PortfolioHolding.account_id,
            PortfolioHolding.asset_id
        ).having(func.count(PortfolioHolding.id) > 1).all()
        
        if duplicates:
            print(f"   ❌ Encontrados {len(duplicates)} holdings duplicados!")
            for dup in duplicates:
                holdings = PortfolioHolding.query.filter_by(
                    account_id=dup.account_id,
                    asset_id=dup.asset_id
                ).all()
                asset = Asset.query.get(dup.asset_id)
                print(f"   - {asset.symbol}: {dup.count} entradas")
                for h in holdings:
                    print(f"     ID {h.id}: qty={h.quantity}, cost={h.total_cost}")
        else:
            print("   ✅ No hay holdings duplicados")
        
        # Transacciones por tipo
        print("\n📝 Transacciones por tipo:")
        from sqlalchemy import func
        tx_types = db.session.query(
            Transaction.transaction_type,
            func.count(Transaction.id).label('count')
        ).group_by(Transaction.transaction_type).all()
        
        for tx_type, count in tx_types:
            print(f"   - {tx_type}: {count}")
        
        # Assets más comunes
        print("\n🏦 Top 10 Assets con más transacciones:")
        top_assets = db.session.query(
            Asset.symbol,
            Asset.currency,
            func.count(Transaction.id).label('tx_count')
        ).join(Transaction).group_by(Asset.id).order_by(func.count(Transaction.id).desc()).limit(10).all()
        
        for symbol, currency, tx_count in top_assets:
            print(f"   - {symbol} ({currency}): {tx_count} transacciones")


if __name__ == '__main__':
    diagnose()

