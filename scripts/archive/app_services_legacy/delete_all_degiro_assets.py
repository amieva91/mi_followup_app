"""
Script para eliminar TODOS los assets de la BD
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.asset import Asset

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("ELIMINANDO TODOS LOS ASSETS")
    print("="*80)
    
    # Contar antes
    total_before = Asset.query.count()
    print(f"\n📊 Assets actuales: {total_before}")
    
    if total_before > 0:
        # Eliminar todos
        Asset.query.delete()
        db.session.commit()
        print(f"✅ {total_before} assets eliminados")
    else:
        print("ℹ️  No hay assets en la BD")
    
    print("\n" + "="*80)
    print("✅ Limpieza completada")
    print("="*80)
    print("\n💡 Ahora puedes reimportar los CSVs")
    print("   - IBKR creará assets con symbol")
    print("   - DeGiro creará assets con symbol=NULL\n")

