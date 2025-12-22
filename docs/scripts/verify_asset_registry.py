"""
Script de verificación rápida del sistema AssetRegistry
"""
from app import create_app, db
from app.models import AssetRegistry, Asset

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("🔍 VERIFICACIÓN DEL SISTEMA AssetRegistry")
    print("="*70)
    
    # 1. Verificar tabla AssetRegistry
    print("\n1️⃣  Verificando tabla AssetRegistry...")
    try:
        count = AssetRegistry.query.count()
        print(f"   ✅ Tabla existe. Registros actuales: {count}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        exit(1)
    
    # 2. Verificar tabla Asset
    print("\n2️⃣  Verificando tabla Asset...")
    try:
        count = Asset.query.count()
        print(f"   ✅ Tabla existe. Assets actuales: {count}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        exit(1)
    
    # 3. Verificar servicio AssetRegistryService
    print("\n3️⃣  Verificando AssetRegistryService...")
    try:
        from app.services.asset_registry_service import AssetRegistryService
        service = AssetRegistryService()
        print(f"   ✅ Servicio inicializado correctamente")
    except Exception as e:
        print(f"   ❌ Error al importar servicio: {e}")
        exit(1)
    
    # 4. Verificar CSVImporterV2
    print("\n4️⃣  Verificando CSVImporterV2...")
    try:
        from app.services.importer_v2 import CSVImporterV2
        print(f"   ✅ Importer V2 disponible")
    except Exception as e:
        print(f"   ❌ Error al importar: {e}")
        exit(1)
    
    # 5. Verificar modelo AssetRegistry
    print("\n5️⃣  Verificando propiedades del modelo AssetRegistry...")
    try:
        # Crear un registro de prueba (no se guarda)
        test_registry = AssetRegistry(
            isin='US0378331005',
            symbol='AAPL',
            yahoo_suffix='',
            ibkr_exchange='NASDAQ',
            currency='USD',
            name='Apple Inc.'
        )
        
        assert test_registry.yahoo_ticker == 'AAPL', "yahoo_ticker fallido"
        assert test_registry.needs_enrichment == False, "needs_enrichment debería ser False"
        
        print(f"   ✅ Propiedades funcionando correctamente")
        print(f"      - yahoo_ticker: {test_registry.yahoo_ticker}")
        print(f"      - needs_enrichment: {test_registry.needs_enrichment}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        exit(1)
    
    # 6. Estadísticas finales
    print("\n6️⃣  Estadísticas actuales:")
    print(f"   • AssetRegistry: {AssetRegistry.query.count()} registros")
    print(f"   • Asset (local): {Asset.query.count()} assets")
    
    if AssetRegistry.query.count() > 0:
        enriched = AssetRegistry.query.filter_by(is_enriched=True).count()
        print(f"   • Enriquecidos: {enriched}/{AssetRegistry.query.count()}")
    
    print("\n" + "="*70)
    print("✅ VERIFICACIÓN COMPLETADA - Sistema listo para pruebas")
    print("="*70)
    print("\n💡 Siguiente paso:")
    print("   1. Iniciar servidor: flask run --host=127.0.0.1 --port=5001")
    print("   2. Ir a: http://127.0.0.1:5001/portfolio/import")
    print("   3. Subir CSVs de IBKR/DeGiro")
    print("   4. Observar el enriquecimiento automático")
    print()

