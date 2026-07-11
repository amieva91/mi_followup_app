#!/usr/bin/env python3
"""
Script para listar assets Forex antes de eliminarlos
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.asset import Asset

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("LISTADO COMPLETO DE ASSETS CON PUNTO EN EL SÍMBOLO")
    print("="*80 + "\n")
    
    # Buscar assets con punto en el símbolo
    forex_assets = Asset.query.filter(Asset.symbol.like('%.%')).all()
    
    if forex_assets:
        print(f"📋 Total assets encontrados: {len(forex_assets)}\n")
        
        for i, asset in enumerate(forex_assets, 1):
            print(f"{i:2}. {asset.symbol:20} | {asset.name:50} | {asset.currency:5} | ISIN: {asset.isin or 'N/A'}")
    else:
        print("✅ No se encontraron assets con punto en el símbolo\n")
    
    print("\n" + "="*80)
    print("ANÁLISIS")
    print("="*80 + "\n")
    
    # Separar por tipo
    forex = []
    stocks = []
    
    for asset in forex_assets:
        symbol = asset.symbol
        # Forex típico: XXX.YYY donde ambos son 3 letras
        parts = symbol.split('.')
        if len(parts) == 2:
            left, right = parts
            if len(left) == 3 and len(right) == 3 and left.isupper() and right.isupper():
                forex.append(asset)
            else:
                stocks.append(asset)
        else:
            stocks.append(asset)
    
    print(f"🔹 Forex típicos (XXX.YYY): {len(forex)}")
    for asset in forex:
        print(f"   - {asset.symbol:15} | {asset.name:40} | {asset.currency}")
    
    print(f"\n🔹 Otros con punto (podrían ser acciones): {len(stocks)}")
    for asset in stocks:
        print(f"   - {asset.symbol:15} | {asset.name:40} | {asset.currency}")
    
    print("\n" + "="*80)

