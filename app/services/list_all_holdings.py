"""
Lista todos los holdings para ver cuáles sobran
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import PortfolioHolding, BrokerAccount


def list_all_holdings():
    """Lista todos los holdings por cuenta"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 80)
        print("TODOS LOS HOLDINGS")
        print("=" * 80)
        
        accounts = BrokerAccount.query.all()
        
        for account in accounts:
            holdings = PortfolioHolding.query.filter_by(account_id=account.id).filter(
                PortfolioHolding.quantity > 0
            ).order_by(PortfolioHolding.quantity.desc()).all()
            
            if not holdings:
                continue
            
            print(f"\n{'='*80}")
            print(f"🏦 {account.broker.name} - {account.account_name}")
            print(f"{'='*80}")
            print(f"Total holdings: {len(holdings)}\n")
            
            for i, h in enumerate(holdings, 1):
                print(f"{i:2d}. {h.asset.symbol:30s} | Qty: {h.quantity:10.0f} | Avg: {h.average_buy_price:8.2f} | Cost: {h.total_cost:12.2f} {h.asset.currency}")


if __name__ == '__main__':
    list_all_holdings()

