#!/usr/bin/env python3
"""
Script para limpiar assets con monedas incorrectas
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Asset

app = create_app('development')

with app.app_context():
    print("\n" + "="*80)
    print("LIMPIEZA DE ASSETS CON MONEDAS INCORRECTAS")
    print("="*80 + "\n")
    
    # Contar todos los assets
    total_assets = Asset.query.count()
    print(f"📊 Total assets antes de limpieza: {total_assets}\n")
    
    # Identificar assets con monedas sospechosas
    # Las monedas válidas son códigos de 3 letras (USD, EUR, HKD, etc.)
    valid_currency_codes = [
        'USD', 'EUR', 'GBP', 'HKD', 'CNY', 'JPY', 'AUD', 'PLN', 'BG',
        'SGD', 'NOK', 'CAD', 'SEK', 'GBX', 'DKK'
    ]
    
    # Buscar assets problemáticos
    problem_assets = []
    for asset in Asset.query.all():
        if asset.currency not in valid_currency_codes:
            problem_assets.append(asset)
    
    print(f"⚠️  Assets con monedas incorrectas: {len(problem_assets)}\n")
    
    if problem_assets:
        print("🗑️  Eliminando assets problemáticos:\n")
        for asset in problem_assets[:10]:  # Mostrar primeros 10
            print(f"   - {asset.symbol}: currency='{asset.currency}'")
        
        if len(problem_assets) > 10:
            print(f"   ... y {len(problem_assets) - 10} más")
        
        # Eliminar
        for asset in problem_assets:
            db.session.delete(asset)
        
        db.session.commit()
        print(f"\n✅ {len(problem_assets)} assets eliminados")
    
    # Contar assets restantes
    remaining_assets = Asset.query.count()
    print(f"\n📊 Assets restantes: {remaining_assets}")
    print("\n✅ Limpieza completada. Ahora puedes reimportar los CSVs.\n")

