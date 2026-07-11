"""
Script para inspeccionar el asset VOLEX
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.asset import Asset

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("INSPECCIONANDO ASSET VOLEX")
    print("="*80)
    
    # Buscar VOLEX
    volex = Asset.query.filter(Asset.name.like('%VOLEX%')).first()
    
    if volex:
        print(f"\n✅ VOLEX encontrado:")
        print(f"   ID: {volex.id}")
        print(f"   symbol: {repr(volex.symbol)}")
        print(f"   name: {repr(volex.name)}")
        print(f"   isin: {repr(volex.isin)}")
        print(f"   asset_type: {repr(volex.asset_type)}")
        print(f"   currency: {repr(volex.currency)}")
        print(f"   exchange: {repr(volex.exchange)}")
        
        print("\n📋 Análisis:")
        if volex.symbol:
            print(f"   ❌ symbol NO está NULL: '{volex.symbol}'")
            print(f"   ❌ Longitud: {len(volex.symbol)}")
            print(f"   ❌ ¿Es igual al nombre? {volex.symbol == volex.name}")
        else:
            print(f"   ✅ symbol está NULL")
            
        print(f"\n   ¿Se mostrará en template?")
        if volex.symbol and volex.symbol != volex.name and len(volex.symbol) < 15:
            print(f"   ❌ SÍ se mostrará: symbol existe, es diferente del nombre, y < 15 chars")
        else:
            print(f"   ✅ NO se mostrará: cumple condiciones de ocultación")
    else:
        print("\n❌ VOLEX no encontrado en BD")
    
    print("\n" + "="*80)
    print("\n💡 Buscando otros assets con 'VOLEX' en symbol...")
    volex_symbols = Asset.query.filter(Asset.symbol.like('%VOLEX%')).all()
    if volex_symbols:
        for asset in volex_symbols:
            print(f"   - ID {asset.id}: symbol='{asset.symbol}', name='{asset.name}'")
    else:
        print("   ✅ No hay assets con 'VOLEX' en symbol")
    
    print("\n")

