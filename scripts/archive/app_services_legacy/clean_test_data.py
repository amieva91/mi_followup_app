"""
Script para limpiar datos de test de la BD
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import User, BrokerAccount, PortfolioHolding, Transaction


def clean_test_data():
    """Limpia datos de test"""
    app = create_app('development')
    
    with app.app_context():
        print("🧹 Limpiando datos de test...")
        
        # Buscar cuenta de test
        account = BrokerAccount.query.filter_by(account_name='Test IBKR Import').first()
        
        if account:
            # Eliminar holdings
            holdings_deleted = PortfolioHolding.query.filter_by(account_id=account.id).delete()
            print(f"   - Holdings eliminados: {holdings_deleted}")
            
            # Eliminar transacciones
            transactions_deleted = Transaction.query.filter_by(account_id=account.id).delete()
            print(f"   - Transacciones eliminadas: {transactions_deleted}")
            
            db.session.commit()
            print("✅ Datos de test limpiados correctamente")
        else:
            print("⚠️  No se encontró cuenta de test")


if __name__ == '__main__':
    clean_test_data()

