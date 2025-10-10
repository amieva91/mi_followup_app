#!/usr/bin/env python3
"""
Script para verificar qué campos de Asset tenemos poblados
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Asset

app = create_app('development')

with app.app_context():
    print("\n" + "="*80)
    print("VERIFICACIÓN DE CAMPOS EN ASSETS")
    print("="*80 + "\n")
    
    total_assets = Asset.query.count()
    print(f"📊 Total assets: {total_assets}\n")
    
    # Verificar primeros 15 assets
    print("🔍 PRIMEROS 15 ASSETS:\n")
    print(f"{'Symbol':<25} {'Exchange':<12} {'Sector':<20} {'Type':<12}")
    print("-" * 80)
    
    for asset in Asset.query.limit(15).all():
        exchange = asset.exchange if asset.exchange else "(vacío)"
        sector = asset.sector if asset.sector else "(vacío)"
        print(f"{asset.symbol:<25} {exchange:<12} {sector:<20} {asset.asset_type:<12}")
    
    # Estadísticas
    print("\n" + "="*80)
    print("ESTADÍSTICAS:")
    print("="*80 + "\n")
    
    with_exchange = Asset.query.filter(Asset.exchange.isnot(None)).filter(Asset.exchange != '').count()
    with_sector = Asset.query.filter(Asset.sector.isnot(None)).filter(Asset.sector != '').count()
    
    print(f"Assets con Exchange: {with_exchange}/{total_assets} ({100*with_exchange/total_assets if total_assets > 0 else 0:.1f}%)")
    print(f"Assets con Sector:   {with_sector}/{total_assets} ({100*with_sector/total_assets if total_assets > 0 else 0:.1f}%)")

