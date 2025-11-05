#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para sincronizar Assets desde AssetRegistry
Útil después de editar manualmente el AssetRegistry
"""

import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.asset import Asset
from app.models.asset_registry import AssetRegistry

app = create_app()

def sync_assets_from_registry():
    """
    Sincroniza todos los Assets con sus correspondientes AssetRegistry
    actualizando symbol, yahoo_suffix, exchange, mic
    """
    with app.app_context():
        print("="*100)
        print("🔄 SINCRONIZANDO ASSETS DESDE ASSETREGISTRY")
        print("="*100)
        
        # Obtener todos los assets con ISIN
        assets = Asset.query.filter(Asset.isin.isnot(None)).all()
        
        if not assets:
            print("\n❌ No hay assets con ISIN en la base de datos")
            return
        
        print(f"\n📊 Total de assets a procesar: {len(assets)}")
        
        updated_count = 0
        not_found_count = 0
        unchanged_count = 0
        
        for asset in assets:
            # Buscar el registro en AssetRegistry
            registry = AssetRegistry.query.filter_by(isin=asset.isin).first()
            
            if not registry:
                print(f"\n⚠️  {asset.isin} ({asset.name or asset.symbol}) - No encontrado en AssetRegistry")
                not_found_count += 1
                continue
            
            # Verificar si hay cambios
            changes = []
            
            if asset.symbol != registry.symbol:
                changes.append(f"symbol: {asset.symbol} → {registry.symbol}")
                asset.symbol = registry.symbol
            
            if asset.yahoo_suffix != registry.yahoo_suffix:
                changes.append(f"yahoo_suffix: {asset.yahoo_suffix} → {registry.yahoo_suffix}")
                asset.yahoo_suffix = registry.yahoo_suffix
            
            if asset.exchange != registry.ibkr_exchange:
                changes.append(f"exchange: {asset.exchange} → {registry.ibkr_exchange}")
                asset.exchange = registry.ibkr_exchange
            
            if asset.mic != registry.mic:
                changes.append(f"mic: {asset.mic} → {registry.mic}")
                asset.mic = registry.mic
            
            if changes:
                print(f"\n✅ {asset.isin} ({asset.name or asset.symbol})")
                for change in changes:
                    print(f"   - {change}")
                updated_count += 1
            else:
                unchanged_count += 1
        
        # Commit de todos los cambios
        if updated_count > 0:
            db.session.commit()
            print(f"\n💾 Cambios guardados en base de datos")
        
        print("\n" + "="*100)
        print("📊 RESUMEN:")
        print(f"   ✅ Assets actualizados:   {updated_count}")
        print(f"   ⚠️  No encontrados:        {not_found_count}")
        print(f"   ℹ️  Sin cambios:           {unchanged_count}")
        print("="*100)
        
        if updated_count > 0:
            print("\n💡 RECOMENDACIÓN: Actualiza los precios ahora con el botón '🔄 Actualizar Precios'")


if __name__ == "__main__":
    sync_assets_from_registry()

