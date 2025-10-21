"""
Script para LIMPIAR COMPLETAMENTE todos los datos de portfolio
Mantiene solo usuarios, categorías de gastos/ingresos, y brokers
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import (
    Asset, AssetRegistry, PriceHistory,
    PortfolioHolding, Transaction, CashFlow, PortfolioMetrics
)

print("\n" + "="*70)
print("⚠️  LIMPIEZA COMPLETA DE DATOS DE PORTFOLIO")
print("="*70)

app = create_app()

with app.app_context():
    print("\n📊 Contando registros actuales...")
    
    counts = {
        'Assets': Asset.query.count(),
        'AssetRegistry': AssetRegistry.query.count(),
        'PriceHistory': PriceHistory.query.count(),
        'PortfolioHolding': PortfolioHolding.query.count(),
        'Transaction': Transaction.query.count(),
        'CashFlow': CashFlow.query.count(),
        'PortfolioMetrics': PortfolioMetrics.query.count(),
    }
    
    total = sum(counts.values())
    
    for table, count in counts.items():
        print(f"   • {table}: {count}")
    
    print(f"\n📊 Total a borrar: {total} registros")
    
    if total == 0:
        print("\n✅ No hay datos para borrar")
        exit(0)
    
    print("\n⚠️  ADVERTENCIA: Esta operación es IRREVERSIBLE")
    response = input("¿Continuar con la limpieza? (escribe 'SI' para confirmar): ")
    
    if response.strip().upper() != 'SI':
        print("\n❌ Operación cancelada")
        exit(0)
    
    print("\n🗑️  Eliminando datos...")
    
    # Orden importante: primero dependencias, luego tablas principales
    deleted = {}
    
    deleted['PortfolioMetrics'] = PortfolioMetrics.query.delete()
    deleted['CashFlow'] = CashFlow.query.delete()
    deleted['Transaction'] = Transaction.query.delete()
    deleted['PortfolioHolding'] = PortfolioHolding.query.delete()
    deleted['PriceHistory'] = PriceHistory.query.delete()
    deleted['Asset'] = Asset.query.delete()
    deleted['AssetRegistry'] = AssetRegistry.query.delete()
    
    db.session.commit()
    
    print("\n✅ Datos eliminados:")
    for table, count in deleted.items():
        if count > 0:
            print(f"   • {table}: {count}")
    
    print("\n" + "="*70)
    print("✅ LIMPIEZA COMPLETADA")
    print("="*70)
    print("\n💡 Ahora puedes importar CSVs desde cero")
    print("   → http://127.0.0.1:5001/portfolio/import")
    print()

