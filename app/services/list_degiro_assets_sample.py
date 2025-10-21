"""
Script para listar assets de DeGiro (sin symbol) con diferentes monedas
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.asset import Asset
from sqlalchemy import or_

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("ASSETS DE DEGIRO (symbol=NULL) - EJEMPLOS PARA TESTING")
    print("="*80)
    
    # Buscar assets sin symbol (DeGiro)
    degiro_assets = Asset.query.filter(
        or_(Asset.symbol == None, Asset.symbol == '')
    ).all()
    
    print(f"\n📊 Total assets sin symbol: {len(degiro_assets)}")
    
    # Agrupar por moneda
    by_currency = {}
    for asset in degiro_assets:
        currency = asset.currency
        if currency not in by_currency:
            by_currency[currency] = []
        by_currency[currency].append(asset)
    
    print(f"\n📋 Monedas encontradas: {', '.join(sorted(by_currency.keys()))}")
    
    # Mostrar 2 ejemplos por moneda
    print("\n" + "="*80)
    print("EJEMPLOS POR MONEDA (para testing con OpenFIGI)")
    print("="*80)
    
    for currency in sorted(by_currency.keys()):
        assets = by_currency[currency][:2]  # Solo 2 por moneda
        print(f"\n💰 {currency} ({len(by_currency[currency])} assets):")
        for asset in assets:
            print(f"   - {asset.name}")
            print(f"     ISIN: {asset.isin}")
            print(f"     Currency: {asset.currency}")
            print(f"     Type: {asset.asset_type}")
            print(f"     Exchange actual: {asset.exchange or 'NULL'}")
            print()
    
    print("="*80)
    print("\n💡 Estos ISINs se usarán para probar OpenFIGI API")
    print()

