#!/usr/bin/env python3
"""
Script para diagnosticar qué monedas se están almacenando en los assets
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Asset, Transaction

app = create_app('development')

with app.app_context():
    print("\n" + "="*80)
    print("DIAGNÓSTICO: MONEDAS EN ASSETS")
    print("="*80 + "\n")
    
    # Todos los assets
    assets = Asset.query.all()
    
    print(f"📊 Total assets: {len(assets)}\n")
    
    # Mostrar primeros 10 con detalle
    print("🔍 PRIMEROS 10 ASSETS:\n")
    for i, asset in enumerate(assets[:10], 1):
        print(f"{i}. {asset.symbol} - {asset.name[:40]}")
        print(f"   Currency almacenada: '{asset.currency}'")
        print(f"   ISIN: {asset.isin}")
        print(f"   Exchange: {asset.exchange}")
        print()
    
    # Buscar assets con monedas raras
    print("\n" + "="*80)
    print("⚠️  ASSETS CON MONEDAS SOSPECHOSAS:")
    print("="*80 + "\n")
    
    valid_currencies = ['USD', 'EUR', 'GBP', 'HKD', 'CNY', 'JPY', 'AUD', 'PLN', 'BG']
    
    for asset in assets:
        if asset.currency not in valid_currencies:
            print(f"❌ {asset.symbol}: currency='{asset.currency}' (debería ser moneda)")
    
    # Ver transacciones de ANXIAN
    print("\n" + "="*80)
    print("🔍 TRANSACCIONES DE ANXIAN:")
    print("="*80 + "\n")
    
    anxian_assets = Asset.query.filter(Asset.symbol.like('%ANXIAN%')).all()
    if anxian_assets:
        for asset in anxian_assets:
            print(f"Asset: {asset.symbol}")
            print(f"  Currency: '{asset.currency}'")
            print(f"  ISIN: {asset.isin}")
            
            txns = Transaction.query.filter_by(asset_id=asset.id).limit(3).all()
            print(f"  Transacciones:")
            for txn in txns:
                print(f"    - {txn.transaction_date}: {txn.transaction_type} | txn.currency='{txn.currency}'")
    else:
        print("No se encontró ANXIAN")

