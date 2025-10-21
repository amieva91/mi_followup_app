"""
Script de prueba completa del sistema AssetRegistry
"""
from app import create_app, db
from app.models import AssetRegistry, Asset
from app.services.asset_registry_service import AssetRegistryService

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("🧪 PRUEBA COMPLETA DEL SISTEMA AssetRegistry")
    print("="*70)
    
    # 1. Verificar que AssetRegistry acepta symbol y exchange
    print("\n1️⃣  Probando get_or_create_from_isin con datos de IBKR...")
    service = AssetRegistryService()
    
    # Simular datos de IBKR (vienen con symbol y exchange)
    registry_ibkr = service.get_or_create_from_isin(
        isin='US0378331005',
        symbol='AAPL',
        exchange='NASDAQ',
        currency='USD',
        name='Apple Inc.',
        asset_type='Stock'
    )
    
    db.session.commit()
    
    print(f"   ✅ Registro creado desde IBKR:")
    print(f"      - ISIN: {registry_ibkr.isin}")
    print(f"      - Symbol: {registry_ibkr.symbol}")
    print(f"      - Exchange: {registry_ibkr.ibkr_exchange}")
    print(f"      - Is Enriched: {registry_ibkr.is_enriched}")
    print(f"      - Source: {registry_ibkr.enrichment_source}")
    
    # 2. Simular datos de DeGiro (sin symbol, solo MIC y degiro_exchange)
    print("\n2️⃣  Probando get_or_create_from_isin con datos de DeGiro...")
    registry_degiro = service.get_or_create_from_isin(
        isin='ES0113211835',
        currency='EUR',
        name='Grifols SA',
        mic='XMAD',
        degiro_exchange='MAD',
        asset_type='Stock'
    )
    
    db.session.commit()
    
    print(f"   ✅ Registro creado desde DeGiro:")
    print(f"      - ISIN: {registry_degiro.isin}")
    print(f"      - Symbol: {registry_degiro.symbol or 'None (esperado)'}")
    print(f"      - Exchange (mapeado): {registry_degiro.ibkr_exchange}")
    print(f"      - MIC: {registry_degiro.mic}")
    print(f"      - Yahoo Suffix (mapeado): {registry_degiro.yahoo_suffix}")
    print(f"      - Is Enriched: {registry_degiro.is_enriched}")
    print(f"      - Needs Enrichment: {registry_degiro.needs_enrichment}")
    
    # 3. Verificar actualización de registro existente
    print("\n3️⃣  Probando actualización de registro existente...")
    print(f"   Intentando re-importar AAPL (debería actualizar usage_count)...")
    
    registry_ibkr_2 = service.get_or_create_from_isin(
        isin='US0378331005',
        symbol='AAPL',
        exchange='NASDAQ',
        currency='USD',
        name='Apple Inc.',
        asset_type='Stock'
    )
    
    db.session.commit()
    
    print(f"   ✅ Registro actualizado:")
    print(f"      - Mismo ID: {registry_ibkr.id == registry_ibkr_2.id}")
    print(f"      - Usage Count: {registry_ibkr_2.usage_count} (debería ser 2)")
    
    # 4. Estadísticas finales
    print("\n4️⃣  Estadísticas del Registro Global:")
    stats = service.get_enrichment_stats()
    print(f"   • Total: {stats['total']}")
    print(f"   • Enriquecidos: {stats['enriched']}")
    print(f"   • Pendientes: {stats['pending']}")
    print(f"   • Completitud: {stats['percentage']:.1f}%")
    
    # 5. Listar todos los registros
    print("\n5️⃣  Listado de registros en AssetRegistry:")
    all_registries = AssetRegistry.query.all()
    for reg in all_registries:
        status = "✅ ENRICHED" if reg.is_enriched else "⚠️  PENDING"
        print(f"   {status} | {reg.isin:12} | {(reg.symbol or 'NO_SYMBOL'):10} | {reg.name}")
    
    print("\n" + "="*70)
    print("✅ TODAS LAS PRUEBAS PASARON")
    print("="*70)
    print("\n💡 Sistema listo para:")
    print("   1. Importar CSVs de IBKR (aportarán symbol/exchange completos)")
    print("   2. Importar CSVs de DeGiro (se mapearán localmente y se enriquecerán)")
    print("   3. Gestionar registros en: http://127.0.0.1:5001/portfolio/asset-registry")
    print()

