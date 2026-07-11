"""
Script para limpiar TODA la BD de portfolio (holdings, transacciones, etc.)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import PortfolioHolding, Transaction, CashFlow, PortfolioMetrics, BrokerAccount


def clean_all():
    """Limpia todos los datos de portfolio"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 80)
        print("LIMPIEZA COMPLETA DE PORTFOLIO")
        print("=" * 80)
        
        print("\n⚠️  ADVERTENCIA: Esto eliminará:")
        print("   - Todos los holdings")
        print("   - Todas las transacciones")
        print("   - Todos los cash flows")
        print("   - Todas las métricas")
        print("   - PERO mantendrá las cuentas de broker")
        
        # Contar antes
        holdings_before = PortfolioHolding.query.count()
        transactions_before = Transaction.query.count()
        cashflows_before = CashFlow.query.count()
        metrics_before = PortfolioMetrics.query.count()
        
        print(f"\n📊 Datos actuales:")
        print(f"   - Holdings: {holdings_before}")
        print(f"   - Transacciones: {transactions_before}")
        print(f"   - Cash flows: {cashflows_before}")
        print(f"   - Métricas: {metrics_before}")
        
        # Eliminar
        print("\n🧹 Limpiando...")
        
        PortfolioMetrics.query.delete()
        print("   ✅ Métricas eliminadas")
        
        CashFlow.query.delete()
        print("   ✅ Cash flows eliminados")
        
        Transaction.query.delete()
        print("   ✅ Transacciones eliminadas")
        
        PortfolioHolding.query.delete()
        print("   ✅ Holdings eliminados")
        
        db.session.commit()
        
        print("\n✅ Limpieza completada")
        print("\n📋 Cuentas de broker (mantenidas):")
        accounts = BrokerAccount.query.all()
        for account in accounts:
            print(f"   - {account.broker.name}: {account.account_name}")
        
        print("\n💡 Ahora puedes re-importar los CSVs con la corrección aplicada")


if __name__ == '__main__':
    clean_all()

