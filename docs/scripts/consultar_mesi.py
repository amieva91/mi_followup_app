"""
Script para consultar todos los assets con MIC='MESI' en la base de datos
Ejecutar: python consultar_mesi.py
"""
from app import create_app, db
from app.models import AssetRegistry, Asset

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("📊 CONSULTA: ASSETS CON MIC = 'MESI'")
    print("="*80 + "\n")
    
    # Consultar AssetRegistry
    registries = AssetRegistry.query.filter_by(mic='MESI').all()
    
    print(f"✅ Total en AssetRegistry: {len(registries)}")
    
    if registries:
        print("\n📋 DETALLE DE ASSETS EN ASSETREGISTRY:")
        print("-" * 80)
        print(f"{'ISIN':<15} {'Nombre':<30} {'País':<15} {'Exchange':<10} {'Yahoo Suffix':<12} {'Symbol':<15}")
        print("-" * 80)
        
        countries = set()
        exchanges = set()
        yahoo_suffixes = set()
        
        for r in registries:
            countries.add(r.country or 'N/A')
            exchanges.add(r.ibkr_exchange or 'N/A')
            yahoo_suffixes.add(r.yahoo_suffix or 'N/A')
            
            print(f"{r.isin:<15} {str(r.name or 'N/A')[:28]:<30} {str(r.country or 'N/A'):<15} {str(r.ibkr_exchange or 'N/A'):<10} {str(r.yahoo_suffix or 'N/A'):<12} {str(r.symbol or 'N/A'):<15}")
        
        print("\n📈 RESUMEN:")
        print(f"   • Países únicos: {sorted(countries)}")
        print(f"   • Exchanges únicos: {sorted(exchanges)}")
        print(f"   • Yahoo Suffixes únicos: {sorted(yahoo_suffixes)}")
        
        # Contar por país
        print("\n📊 DISTRIBUCIÓN POR PAÍS:")
        from collections import Counter
        country_counts = Counter(r.country or 'N/A' for r in registries)
        for country, count in sorted(country_counts.items()):
            print(f"   • {country}: {count} assets")
        
        # Contar por exchange
        print("\n📊 DISTRIBUCIÓN POR EXCHANGE:")
        exchange_counts = Counter(r.ibkr_exchange or 'N/A' for r in registries)
        for exchange, count in sorted(exchange_counts.items()):
            print(f"   • {exchange}: {count} assets")
        
        # Casos problemáticos (MESI pero país != ES)
        print("\n⚠️  CASOS PROBLEMÁTICOS (MESI pero país != ES):")
        problematic = [r for r in registries if r.country and r.country not in ['ES', 'Spain', None]]
        if problematic:
            for r in problematic:
                print(f"   • {r.isin} | {r.name} | País: {r.country} | Exchange: {r.ibkr_exchange} | Yahoo: {r.yahoo_suffix}")
        else:
            print("   ✅ No se encontraron casos problemáticos")
    
    # Consultar Assets locales (por usuario)
    print("\n" + "="*80)
    print("📊 CONSULTA: ASSETS LOCALES CON MIC = 'MESI'")
    print("="*80 + "\n")
    
    assets = Asset.query.filter_by(mic='MESI').all()
    print(f"✅ Total en Assets (todos los usuarios): {len(assets)}")
    
    if assets:
        print("\n📋 DETALLE (primeros 10):")
        print("-" * 80)
        print(f"{'ISIN':<15} {'Nombre':<30} {'País':<15} {'Exchange':<10} {'Yahoo Suffix':<12}")
        print("-" * 80)
        
        for a in assets[:10]:
            print(f"{a.isin:<15} {str(a.name or 'N/A')[:28]:<30} {str(a.country or 'N/A'):<15} {str(a.exchange or 'N/A'):<10} {str(a.yahoo_suffix or 'N/A'):<12}")
        
        if len(assets) > 10:
            print(f"\n   ... y {len(assets) - 10} más")
    
    # Consultar mapeos en MappingRegistry
    print("\n" + "="*80)
    print("📊 CONSULTA: MAPEOS PARA MESI EN MAPPINGREGISTRY")
    print("="*80 + "\n")
    
    from app.models import MappingRegistry
    
    mesi_mappings = MappingRegistry.query.filter_by(
        mapping_type='MIC_TO_YAHOO',
        source_key='MESI'
    ).all()
    
    print(f"✅ Total de mapeos MESI → Yahoo: {len(mesi_mappings)}")
    
    for m in mesi_mappings:
        print(f"   • MESI → {m.target_value} | País: {m.country or 'N/A'} | Desc: {m.description or 'N/A'}")
    
    # Consultar mapeos de exchange EO
    print("\n" + "="*80)
    print("📊 CONSULTA: MAPEOS PARA EXCHANGE 'EO' EN MAPPINGREGISTRY")
    print("="*80 + "\n")
    
    eo_mappings = MappingRegistry.query.filter_by(
        mapping_type='EXCHANGE_TO_YAHOO',
        source_key='EO'
    ).all()
    
    print(f"✅ Total de mapeos EO → Yahoo: {len(eo_mappings)}")
    
    for m in eo_mappings:
        print(f"   • EO → {m.target_value} | País: {m.country or 'N/A'} | Desc: {m.description or 'N/A'}")
    
    print("\n" + "="*80)
    print("✅ CONSULTA COMPLETADA")
    print("="*80 + "\n")

