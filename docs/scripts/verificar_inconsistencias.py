"""
Script para verificar inconsistencias entre entornos
Ejecutar en dev y prod para comparar resultados
"""
from app import create_app, db
from app.models import AssetRegistry, Asset

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔍 VERIFICACIÓN DE INCONSISTENCIAS")
    print("="*80 + "\n")
    
    # 1. Verificar Volex
    print("1️⃣  VERIFICANDO VOLEX (GB0009390070):")
    print("-" * 80)
    
    volex_registry = AssetRegistry.query.filter_by(isin='GB0009390070').first()
    if volex_registry:
        print(f"AssetRegistry:")
        print(f"  • ISIN: {volex_registry.isin}")
        print(f"  • Symbol: {volex_registry.symbol}")
        print(f"  • MIC: {volex_registry.mic}")
        print(f"  • Yahoo Suffix: {volex_registry.yahoo_suffix}")
        print(f"  • Yahoo Ticker: {volex_registry.yahoo_ticker}")
        print(f"  • Exchange: {volex_registry.ibkr_exchange}")
        print(f"  • Country: {volex_registry.country}")
        print(f"  • Is Enriched: {volex_registry.is_enriched}")
        print(f"  • Enrichment Source: {volex_registry.enrichment_source}")
    else:
        print("  ❌ No se encontró en AssetRegistry")
    
    volex_assets = Asset.query.filter_by(isin='GB0009390070').all()
    if volex_assets:
        print(f"\nAssets locales ({len(volex_assets)}):")
        for asset in volex_assets:
            print(f"  • ID: {asset.id}")
            print(f"    Symbol: {asset.symbol}")
            print(f"    Yahoo Suffix: {asset.yahoo_suffix}")
            print(f"    Yahoo Ticker: {asset.yahoo_ticker}")
            print(f"    Current Price: {asset.current_price} {asset.currency if asset.currency else ''}")
            print(f"    Last Update: {asset.last_price_update}")
    else:
        print("  ❌ No se encontró en Assets")
    
    # 2. Verificar ANDEAN PRECIOUS METALS
    print("\n" + "="*80)
    print("2️⃣  VERIFICANDO ANDEAN PRECIOUS METALS (CA03349X1015):")
    print("-" * 80)
    
    andean_registry = AssetRegistry.query.filter_by(isin='CA03349X1015').first()
    if andean_registry:
        print(f"AssetRegistry:")
        print(f"  • ISIN: {andean_registry.isin}")
        print(f"  • Symbol: {andean_registry.symbol}")
        print(f"  • MIC: {andean_registry.mic}")
        print(f"  • Yahoo Suffix: {andean_registry.yahoo_suffix}")
        print(f"  • Yahoo Ticker: {andean_registry.yahoo_ticker}")
        print(f"  • Exchange: {andean_registry.ibkr_exchange}")
        print(f"  • Country: {andean_registry.country}")
    else:
        print("  ❌ No se encontró en AssetRegistry")
    
    andean_assets = Asset.query.filter_by(isin='CA03349X1015').all()
    if andean_assets:
        print(f"\nAssets locales ({len(andean_assets)}):")
        for asset in andean_assets:
            print(f"  • ID: {asset.id}")
            print(f"    Symbol: {asset.symbol}")
            print(f"    Yahoo Suffix: {asset.yahoo_suffix}")
            print(f"    Yahoo Ticker: {asset.yahoo_ticker}")
            print(f"    Current Price: {asset.current_price} {asset.currency if asset.currency else ''}")
            print(f"    Last Update: {asset.last_price_update}")
    else:
        print("  ❌ No se encontró en Assets")
    
    # 3. Verificar assets que necesitan enriquecimiento
    print("\n" + "="*80)
    print("3️⃣  ASSETS QUE NECESITAN ENRIQUECIMIENTO:")
    print("-" * 80)
    
    registries_needing = AssetRegistry.query.filter(
        db.or_(
            AssetRegistry.symbol.is_(None),
            AssetRegistry.mic.is_(None)
        )
    ).all()
    
    print(f"Total: {len(registries_needing)}")
    for r in registries_needing[:10]:  # Primeros 10
        missing = []
        if not r.symbol:
            missing.append('Symbol')
        if not r.mic:
            missing.append('MIC')
        print(f"  • {r.isin} | {r.name or 'N/A'} | Falta: {', '.join(missing)}")
    
    if len(registries_needing) > 10:
        print(f"  ... y {len(registries_needing) - 10} más")
    
    # 4. Verificar mapeo MESI
    print("\n" + "="*80)
    print("4️⃣  VERIFICANDO MAPEO MESI:")
    print("-" * 80)
    
    from app.models import MappingRegistry
    
    mesi_mapping = MappingRegistry.query.filter_by(
        mapping_type='MIC_TO_YAHOO',
        source_key='MESI'
    ).first()
    
    if mesi_mapping:
        print(f"  ⚠️  MESI ESTÁ MAPEADO:")
        print(f"     MESI → {mesi_mapping.target_value}")
        print(f"     País: {mesi_mapping.country}")
        print(f"     Descripción: {mesi_mapping.description}")
        print(f"     Estado: {'Activo' if mesi_mapping.is_active else 'Inactivo'}")
    else:
        print(f"  ✅ MESI NO está mapeado (correcto para fallback a exchange)")
    
    # 5. Verificar mapeo EO
    print("\n" + "="*80)
    print("5️⃣  VERIFICANDO MAPEO EO:")
    print("-" * 80)
    
    eo_mapping = MappingRegistry.query.filter_by(
        mapping_type='EXCHANGE_TO_YAHOO',
        source_key='EO'
    ).first()
    
    if eo_mapping:
        print(f"  ✅ EO está mapeado:")
        print(f"     EO → {eo_mapping.target_value}")
        print(f"     País: {eo_mapping.country}")
        print(f"     Descripción: {eo_mapping.description}")
    else:
        print(f"  ❌ EO NO está mapeado (necesario para Volex)")
    
    # 6. Estadísticas de enriquecimiento
    print("\n" + "="*80)
    print("6️⃣  ESTADÍSTICAS DE ENRIQUECIMIENTO:")
    print("-" * 80)
    
    total_registries = AssetRegistry.query.count()
    enriched = AssetRegistry.query.filter_by(is_enriched=True).count()
    with_symbol = AssetRegistry.query.filter(AssetRegistry.symbol.isnot(None)).count()
    with_mic = AssetRegistry.query.filter(AssetRegistry.mic.isnot(None)).count()
    needing = AssetRegistry.query.filter(
        db.or_(
            AssetRegistry.symbol.is_(None),
            AssetRegistry.mic.is_(None)
        )
    ).count()
    
    print(f"  • Total AssetRegistry: {total_registries}")
    print(f"  • Enriquecidos (is_enriched=True): {enriched}")
    print(f"  • Con Symbol: {with_symbol}")
    print(f"  • Con MIC: {with_mic}")
    print(f"  • Necesitan enriquecimiento: {needing}")
    
    print("\n" + "="*80)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("="*80 + "\n")
    print("💡 Ejecuta este script en ambos entornos y compara los resultados")
    print()

