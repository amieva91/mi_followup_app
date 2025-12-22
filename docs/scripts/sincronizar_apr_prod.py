"""
Script para sincronizar el asset APR en PROD
Cambiar de 0RI1/0RI1.L a APR/APR.WA para coincidir con DEV
"""
from app import create_app, db
from app.models import Asset, AssetRegistry, PortfolioHolding

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔧 SINCRONIZANDO ASSET APR EN PRODUCCIÓN")
    print("="*80 + "\n")
    
    isin = 'PLATPRT00018'
    
    # 1. Buscar Asset con ISIN
    print("1️⃣  BUSCANDO ASSET EN BD:")
    print("-" * 80)
    asset = Asset.query.filter_by(isin=isin).first()
    
    if not asset:
        print(f"❌ No se encontró asset con ISIN {isin}")
        exit(1)
    
    print(f"Asset encontrado:")
    print(f"  • ID: {asset.id}")
    print(f"  • ISIN: {asset.isin}")
    print(f"  • Symbol actual: {asset.symbol}")
    print(f"  • Yahoo Suffix actual: {asset.yahoo_suffix}")
    print(f"  • Yahoo Ticker actual: {asset.yahoo_ticker}")
    print(f"  • Exchange: {asset.exchange}")
    print(f"  • MIC: {asset.mic}")
    print(f"  • Current Price: {asset.current_price} {asset.currency}")
    
    # 2. Buscar AssetRegistry
    print("\n2️⃣  BUSCANDO ASSETREGISTRY:")
    print("-" * 80)
    registry = AssetRegistry.query.filter_by(isin=isin).first()
    
    if not registry:
        print(f"❌ No se encontró AssetRegistry con ISIN {isin}")
        exit(1)
    
    print(f"AssetRegistry encontrado:")
    print(f"  • ISIN: {registry.isin}")
    print(f"  • Symbol actual: {registry.symbol}")
    print(f"  • Yahoo Suffix actual: {registry.yahoo_suffix}")
    print(f"  • Yahoo Ticker actual: {registry.yahoo_ticker}")
    print(f"  • Exchange: {registry.ibkr_exchange}")
    print(f"  • MIC: {registry.mic}")
    
    # 3. Verificar que el MIC es XWAR (Warsaw)
    if registry.mic != 'XWAR':
        print(f"\n⚠️  ADVERTENCIA: MIC es {registry.mic}, no XWAR")
        print("   El asset debería usar .WA (Warsaw), no .L (London)")
    
    # 4. Aplicar correcciones
    print("\n3️⃣  APLICANDO CORRECCIONES:")
    print("-" * 80)
    
    # Valores correctos (como en DEV)
    correct_symbol = 'APR'
    correct_suffix = '.WA'
    correct_ticker = 'APR.WA'
    
    changes_made = []
    
    # Corregir Asset
    if asset.symbol != correct_symbol:
        print(f"  • Asset.symbol: {asset.symbol} → {correct_symbol}")
        asset.symbol = correct_symbol
        changes_made.append('Asset.symbol')
    
    if asset.yahoo_suffix != correct_suffix:
        print(f"  • Asset.yahoo_suffix: {asset.yahoo_suffix} → {correct_suffix}")
        asset.yahoo_suffix = correct_suffix
        changes_made.append('Asset.yahoo_suffix')
    
    # Corregir AssetRegistry
    if registry.symbol != correct_symbol:
        print(f"  • AssetRegistry.symbol: {registry.symbol} → {correct_symbol}")
        registry.symbol = correct_symbol
        changes_made.append('AssetRegistry.symbol')
    
    if registry.yahoo_suffix != correct_suffix:
        print(f"  • AssetRegistry.yahoo_suffix: {registry.yahoo_suffix} → {correct_suffix}")
        registry.yahoo_suffix = correct_suffix
        changes_made.append('AssetRegistry.yahoo_suffix')
    
    # 5. Guardar cambios
    if changes_made:
        print(f"\n4️⃣  GUARDANDO CAMBIOS:")
        print("-" * 80)
        try:
            db.session.commit()
            print(f"✅ {len(changes_made)} cambios guardados exitosamente")
            print(f"   Campos modificados: {', '.join(changes_made)}")
        except Exception as e:
            print(f"❌ Error al guardar: {e}")
            db.session.rollback()
            exit(1)
    else:
        print("\nℹ️  No se necesitaron cambios (ya está correcto)")
    
    # 6. Verificar resultado
    print("\n5️⃣  VERIFICACIÓN FINAL:")
    print("-" * 80)
    
    # Refrescar desde BD
    db.session.refresh(asset)
    db.session.refresh(registry)
    
    print(f"Asset:")
    print(f"  • Symbol: {asset.symbol}")
    print(f"  • Yahoo Suffix: {asset.yahoo_suffix}")
    print(f"  • Yahoo Ticker: {asset.yahoo_ticker}")
    
    print(f"\nAssetRegistry:")
    print(f"  • Symbol: {registry.symbol}")
    print(f"  • Yahoo Suffix: {registry.yahoo_suffix}")
    print(f"  • Yahoo Ticker: {registry.yahoo_ticker}")
    
    # Verificar holdings
    holdings = PortfolioHolding.query.filter_by(asset_id=asset.id).all()
    if holdings:
        print(f"\nHoldings:")
        for h in holdings:
            print(f"  • {h.quantity} unidades")
    
    # Verificar que coincida con DEV
    if asset.symbol == 'APR' and asset.yahoo_suffix == '.WA':
        print("\n✅ Sincronización completada correctamente")
        print("   El asset ahora coincide con DEV (APR/APR.WA)")
    else:
        print("\n⚠️  La sincronización puede no estar completa")
        print(f"   Symbol: {asset.symbol}, Suffix: {asset.yahoo_suffix}")
    
    print("\n" + "="*80)
    print("✅ PROCESO COMPLETADO")
    print("="*80 + "\n")
    print("💡 Nota: El precio puede ser diferente porque .WA y .L son exchanges diferentes")
    print("   Se recomienda actualizar los precios después de este cambio")
    print()

