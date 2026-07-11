"""
Script para enriquecer assets existentes con datos de OpenFIGI
Útil después de una importación rápida sin enriquecimiento
"""
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Asset
from app.services.market_data import AssetEnricher
from time import sleep

print("\n" + "="*70)
print("ENRIQUECIMIENTO DE ASSETS EXISTENTES")
print("="*70)

# Crear contexto de aplicación
app = create_app()

with app.app_context():
    # Buscar assets que necesitan enriquecimiento
    # Criterio: tienen ISIN y MIC pero no tienen symbol
    assets_to_enrich = Asset.query.filter(
        Asset.isin.isnot(None),
        Asset.mic.isnot(None),
        Asset.symbol.is_(None)
    ).all()
    
    print(f"\n📊 Assets encontrados que necesitan enriquecimiento: {len(assets_to_enrich)}")
    
    if len(assets_to_enrich) == 0:
        print("✅ Todos los assets ya están enriquecidos!")
        exit(0)
    
    print(f"⏱️  Tiempo estimado: ~{len(assets_to_enrich) * 0.15:.0f} segundos")
    
    # Preguntar confirmación
    response = input(f"\n¿Continuar con el enriquecimiento? (s/N): ")
    if response.lower() != 's':
        print("❌ Cancelado")
        exit(0)
    
    print("\n" + "-"*70)
    
    enricher = AssetEnricher()
    
    stats = {
        'enriquecidos': 0,
        'fallidos': 0,
        'sin_cambios': 0
    }
    
    for idx, asset in enumerate(assets_to_enrich, 1):
        print(f"\n[{idx}/{len(assets_to_enrich)}] {asset.name[:40]}")
        print(f"    ISIN: {asset.isin} | MIC: {asset.mic}")
        
        try:
            # Enriquecer
            enriched_data = enricher.enrich_from_isin(
                isin=asset.isin,
                currency=asset.currency,
                degiro_exchange=None,  # Ya tenemos exchange
                degiro_mic=asset.mic
            )
            
            if enriched_data and enriched_data.get('symbol'):
                # Actualizar asset
                asset.symbol = enriched_data['symbol']
                
                if enriched_data.get('name'):
                    asset.name = enriched_data['name']
                
                if enriched_data.get('asset_type'):
                    asset.asset_type = enriched_data['asset_type']
                
                if enriched_data.get('exchange') and not asset.exchange:
                    asset.exchange = enriched_data['exchange']
                
                # MIC prevalece si OpenFIGI lo proporciona
                if enriched_data.get('mic'):
                    asset.mic = enriched_data['mic']
                    # Recalcular yahoo_suffix con el nuevo MIC
                    from app.services.market_data.mappers import YahooSuffixMapper
                    asset.yahoo_suffix = YahooSuffixMapper.mic_to_yahoo_suffix(enriched_data['mic'])
                
                db.session.commit()
                
                print(f"    ✅ Symbol: {asset.symbol} | Yahoo: {asset.yahoo_ticker}")
                print(f"       Fuente: {enriched_data.get('source', 'N/A')}")
                stats['enriquecidos'] += 1
            else:
                print(f"    ⚠️  OpenFIGI no devolvió datos")
                stats['sin_cambios'] += 1
        
        except Exception as e:
            print(f"    ❌ Error: {str(e)[:60]}")
            stats['fallidos'] += 1
        
        # Rate limiting
        if idx < len(assets_to_enrich):
            sleep(0.1)
    
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    print(f"""
✅ Enriquecidos exitosamente: {stats['enriquecidos']}
⚠️  Sin cambios (sin datos):   {stats['sin_cambios']}
❌ Fallidos:                    {stats['fallidos']}

Total procesados: {len(assets_to_enrich)}
""")
    
    if stats['enriquecidos'] > 0:
        print("✅ Enriquecimiento completado!")
        print("💡 Ahora puedes usar asset.yahoo_ticker para actualizar precios")
    
    print()

