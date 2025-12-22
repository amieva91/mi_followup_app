#!/usr/bin/env python3
"""
Script para formateo total de la base de datos
Elimina TODOS los datos incluyendo mapeos y AssetRegistry
Luego ejecuta populate_mappings.py para recrear los mapeos
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import (
    Asset, AssetRegistry, PriceHistory,
    PortfolioHolding, Transaction, CashFlow, PortfolioMetrics,
    BrokerAccount, MappingRegistry, MetricsCache
)

def format_database_complete(skip_confirmation=False):
    """Formatea completamente la BD eliminando todos los datos"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("⚠️  FORMATEO TOTAL DE BASE DE DATOS")
        print("="*80)
        
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
            'MappingRegistry': MappingRegistry.query.count(),
            'MetricsCache': MetricsCache.query.count(),
        }
        
        total = sum(counts.values())
        
        for table, count in counts.items():
            if count > 0:
                print(f"   • {table}: {count}")
        
        print(f"\n📊 Total a borrar: {total} registros")
        
        if total == 0:
            print("\n✅ No hay datos para borrar")
            print("   Procediendo a ejecutar populate_mappings.py...")
        else:
            print("\n⚠️  ADVERTENCIA: Esta operación es IRREVERSIBLE")
            print("   Se eliminarán:")
            print("   - Todos los assets y holdings")
            print("   - Todas las transacciones")
            print("   - Todos los cash flows y métricas")
            print("   - Todas las cuentas de broker")
            print("   - AssetRegistry (registro global de assets)")
            print("   - MappingRegistry (todos los mapeos)")
            print("   - MetricsCache (caché de métricas)")
            print("\n   Se mantendrán:")
            print("   - Usuarios")
            print("   - Brokers (configuración)")
            print("   - Categorías de gastos e ingresos")
            
            if not skip_confirmation:
                response = input("\n¿Continuar con el formateo? (escribe 'SI' para confirmar): ")
                
                if response.strip().upper() != 'SI':
                    print("\n❌ Operación cancelada")
                    return
            else:
                print("\n⚠️  Saltando confirmación (modo automático)")
        
        print("\n🗑️  Eliminando datos...")
        
        deleted = {}
        
        try:
            # Orden importante: primero dependencias, luego tablas principales
            
            deleted['MetricsCache'] = MetricsCache.query.delete()
            print(f"   ✅ MetricsCache: {deleted['MetricsCache']} eliminados")
            
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
            
            deleted['AssetRegistry'] = AssetRegistry.query.delete()
            print(f"   ✅ AssetRegistry: {deleted['AssetRegistry']} eliminados")
            
            deleted['MappingRegistry'] = MappingRegistry.query.delete()
            print(f"   ✅ MappingRegistry: {deleted['MappingRegistry']} eliminados")
            
            deleted['BrokerAccount'] = BrokerAccount.query.delete()
            print(f"   ✅ BrokerAccount: {deleted['BrokerAccount']} eliminados")
            
            db.session.commit()
            
            print("\n✅ Formateo completado exitosamente")
            print(f"\n📋 Resumen de eliminación:")
            for table, count in deleted.items():
                print(f"   • {table}: {count} registros eliminados")
            
            print("\n🔄 Ejecutando populate_mappings.py...")
            print("-" * 80)
            
            # Ejecutar populate_mappings.py
            import subprocess
            result = subprocess.run(
                [sys.executable, 'populate_mappings.py'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(result.stdout)
                print("✅ Mapeos recreados exitosamente")
            else:
                print("❌ Error al ejecutar populate_mappings.py:")
                print(result.stderr)
                print("\n⚠️  Puedes ejecutarlo manualmente con: python populate_mappings.py")
            
            print("\n" + "="*80)
            print("✅ PROCESO COMPLETADO")
            print("="*80)
            print("\n📋 Próximos pasos:")
            print("   1. ✅ Mapeos recreados (si populate_mappings.py se ejecutó correctamente)")
            print("   2. Crear nuevas cuentas de broker desde la UI")
            print("   3. Importar CSVs desde cero")
            print("   4. Actualizar precios desde la UI")
            print()
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error durante el formateo: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    import sys
    # Si se pasa --yes o -y, saltar confirmación
    skip_confirmation = '--yes' in sys.argv or '-y' in sys.argv
    format_database_complete(skip_confirmation=skip_confirmation)

