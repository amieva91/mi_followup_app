#!/usr/bin/env python3
"""
Script para formatear producción y partir de cero
Elimina todos los datos de portfolio pero mantiene usuarios y configuración
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import (
    Asset, AssetRegistry, PriceHistory,
    PortfolioHolding, Transaction, CashFlow, PortfolioMetrics,
    BrokerAccount, Broker
)

def format_production():
    """Formatea producción eliminando todos los datos de portfolio"""
    app = create_app('production')
    
    with app.app_context():
        print("\n" + "="*70)
        print("⚠️  FORMATEO DE PRODUCCIÓN - PARTIR DE CERO")
        print("="*70)
        
        print("\n📊 Contando registros actuales...")
        
        counts = {
            'Assets': Asset.query.count(),
            'AssetRegistry': AssetRegistry.query.count(),
            'PriceHistory': PriceHistory.query.count(),
            'PortfolioHolding': PortfolioHolding.query.count(),
            'Transaction': Transaction.query.count(),
            'CashFlow': CashFlow.query.count(),
            'PortfolioMetrics': PortfolioMetrics.query.count(),
            'BrokerAccount': BrokerAccount.query.count(),
        }
        
        total = sum(counts.values())
        
        for table, count in counts.items():
            if count > 0:
                print(f"   • {table}: {count}")
        
        print(f"\n📊 Total a borrar: {total} registros")
        
        if total == 0:
            print("\n✅ No hay datos para borrar")
            return
        
        print("\n⚠️  ADVERTENCIA: Esta operación es IRREVERSIBLE")
        print("   Se eliminarán:")
        print("   - Todos los assets y holdings")
        print("   - Todas las transacciones")
        print("   - Todos los cash flows y métricas")
        print("   - Todas las cuentas de broker")
        print("   - PERO se mantendrán: usuarios, categorías, AssetRegistry global")
        
        response = input("\n¿Continuar con el formateo? (escribe 'SI' para confirmar): ")
        
        if response.strip().upper() != 'SI':
            print("\n❌ Operación cancelada")
            return
        
        print("\n🗑️  Eliminando datos...")
        
        # Orden importante: primero dependencias, luego tablas principales
        deleted = {}
        
        try:
            deleted['PortfolioMetrics'] = PortfolioMetrics.query.delete()
            print(f"   ✅ PortfolioMetrics: {deleted['PortfolioMetrics']} eliminados")
            
            deleted['CashFlow'] = CashFlow.query.delete()
            print(f"   ✅ CashFlow: {deleted['CashFlow']} eliminados")
            
            deleted['Transaction'] = Transaction.query.delete()
            print(f"   ✅ Transaction: {deleted['Transaction']} eliminados")
            
            deleted['PortfolioHolding'] = PortfolioHolding.query.count()
            PortfolioHolding.query.delete()
            print(f"   ✅ PortfolioHolding: {deleted['PortfolioHolding']} eliminados")
            
            deleted['PriceHistory'] = PriceHistory.query.delete()
            print(f"   ✅ PriceHistory: {deleted['PriceHistory']} eliminados")
            
            deleted['Asset'] = Asset.query.delete()
            print(f"   ✅ Asset: {deleted['Asset']} eliminados")
            
            deleted['BrokerAccount'] = BrokerAccount.query.delete()
            print(f"   ✅ BrokerAccount: {deleted['BrokerAccount']} eliminados")
            
            # AssetRegistry se mantiene (es global compartida)
            # Broker se mantiene (configuración)
            
            db.session.commit()
            
            print("\n✅ Formateo completado exitosamente")
            print("\n📋 Datos mantenidos:")
            print(f"   • AssetRegistry: {AssetRegistry.query.count()} registros (global compartida)")
            print(f"   • Broker: {Broker.query.count()} brokers (configuración)")
            
            print("\n🔄 Próximos pasos:")
            print("   1. Reiniciar la aplicación")
            print("   2. Crear nuevas cuentas de broker")
            print("   3. Importar CSVs desde cero")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error durante el formateo: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    format_production()

