#!/usr/bin/env python3
"""
Script para limpiar assets incorrectos (Forex y asset_type incorrecto)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.asset import Asset

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("LIMPIEZA DE ASSETS INCORRECTOS")
    print("="*80 + "\n")
    
    # 1. Eliminar assets Forex (con punto en el símbolo)
    forex_assets = Asset.query.filter(Asset.symbol.like('%.%')).all()
    
    if forex_assets:
        print(f"📋 Assets Forex encontrados (símbolo con punto): {len(forex_assets)}")
        for asset in forex_assets:
            print(f"  - {asset.symbol} ({asset.currency})")
        
        for asset in forex_assets:
            db.session.delete(asset)
        
        print(f"\n✅ {len(forex_assets)} assets Forex eliminados\n")
    else:
        print("✅ No se encontraron assets Forex\n")
    
    # 2. Eliminar R2US para que se vuelva a crear correctamente
    r2us = Asset.query.filter_by(symbol='R2US').first()
    if r2us:
        print(f"📋 R2US encontrado:")
        print(f"  - Nombre: {r2us.name}")
        print(f"  - Tipo actual: {r2us.asset_type}")
        print(f"  - ISIN: {r2us.isin}")
        
        db.session.delete(r2us)
        print(f"\n✅ R2US eliminado (se recreará como ETF en la importación)\n")
    else:
        print("ℹ️  R2US no encontrado en BD\n")
    
    # Commit
    db.session.commit()
    
    print("="*80)
    print("✅ Limpieza completada")
    print("="*80 + "\n")
    
    print("💡 Ahora puedes reimportar los CSVs:")
    print("   1. Los assets Forex NO se crearán")
    print("   2. R2US se creará correctamente como ETF")
    print()
