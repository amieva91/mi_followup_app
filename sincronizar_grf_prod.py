"""
Script para sincronizar el asset GRF en PROD
Añadir suffix .MC para coincidir con DEV
"""
from app import create_app, db
from app.models import Asset, AssetRegistry

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔧 SINCRONIZANDO ASSET GRF EN PRODUCCIÓN")
    print("="*80 + "\n")
    
    isin = 'ES0171996087'
    
    # Buscar Asset
    asset = Asset.query.filter_by(isin=isin).first()
    if not asset:
        print(f"❌ No se encontró asset con ISIN {isin}")
        exit(1)
    
    print(f"Asset encontrado:")
    print(f"  • Symbol: {asset.symbol}")
    print(f"  • Yahoo Suffix actual: {asset.yahoo_suffix or '(vacío)'}")
    print(f"  • Yahoo Ticker actual: {asset.yahoo_ticker}")
    print(f"  • MIC: {asset.mic}")
    
    # Buscar AssetRegistry
    registry = AssetRegistry.query.filter_by(isin=isin).first()
    if not registry:
        print(f"❌ No se encontró AssetRegistry con ISIN {isin}")
        exit(1)
    
    print(f"\nAssetRegistry encontrado:")
    print(f"  • Symbol: {registry.symbol}")
    print(f"  • Yahoo Suffix actual: {registry.yahoo_suffix or '(vacío)'}")
    print(f"  • Yahoo Ticker actual: {registry.yahoo_ticker}")
    print(f"  • MIC: {registry.mic}")
    
    # Verificar que el MIC es XMAD (Madrid)
    if registry.mic != 'XMAD':
        print(f"\n⚠️  ADVERTENCIA: MIC es {registry.mic}, no XMAD")
    
    # Aplicar correcciones
    print("\n🔧 APLICANDO CORRECCIONES:")
    print("-" * 80)
    
    correct_suffix = '.MC'
    changes_made = []
    
    # Corregir Asset
    if asset.yahoo_suffix != correct_suffix:
        print(f"  • Asset.yahoo_suffix: {asset.yahoo_suffix or '(vacío)'} → {correct_suffix}")
        asset.yahoo_suffix = correct_suffix
        changes_made.append('Asset.yahoo_suffix')
    
    # Corregir AssetRegistry
    if registry.yahoo_suffix != correct_suffix:
        print(f"  • AssetRegistry.yahoo_suffix: {registry.yahoo_suffix or '(vacío)'} → {correct_suffix}")
        registry.yahoo_suffix = correct_suffix
        changes_made.append('AssetRegistry.yahoo_suffix')
    
    # Guardar cambios
    if changes_made:
        print(f"\n💾 GUARDANDO CAMBIOS:")
        print("-" * 80)
        try:
            db.session.commit()
            print(f"✅ {len(changes_made)} cambios guardados exitosamente")
        except Exception as e:
            print(f"❌ Error al guardar: {e}")
            db.session.rollback()
            exit(1)
    else:
        print("\nℹ️  No se necesitaron cambios (ya está correcto)")
    
    # Verificar resultado
    print("\n✅ VERIFICACIÓN FINAL:")
    print("-" * 80)
    db.session.refresh(asset)
    db.session.refresh(registry)
    
    print(f"Asset:")
    print(f"  • Yahoo Suffix: {asset.yahoo_suffix}")
    print(f"  • Yahoo Ticker: {asset.yahoo_ticker}")
    
    print(f"\nAssetRegistry:")
    print(f"  • Yahoo Suffix: {registry.yahoo_suffix}")
    print(f"  • Yahoo Ticker: {registry.yahoo_ticker}")
    
    if asset.yahoo_suffix == '.MC' and registry.yahoo_suffix == '.MC':
        print("\n✅ Sincronización completada correctamente")
        print("   El asset ahora coincide con DEV (GRF.MC)")
    else:
        print("\n⚠️  La sincronización puede no estar completa")
    
    print("\n" + "="*80)
    print("✅ PROCESO COMPLETADO")
    print("="*80 + "\n")

