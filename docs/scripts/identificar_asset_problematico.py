"""
Script para identificar el asset problemático APR/0RI1
"""
from app import create_app, db
from app.models import Asset, AssetRegistry, PortfolioHolding

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔍 IDENTIFICANDO ASSET PROBLEMÁTICO (APR/0RI1)")
    print("="*80 + "\n")
    
    # Buscar APR
    print("1️⃣  BUSCANDO 'APR':")
    print("-" * 80)
    apr_assets = Asset.query.filter(
        Asset.symbol.like('%APR%')
    ).all()
    
    # También buscar por yahoo_suffix que contenga WA
    apr_assets_wa = Asset.query.filter(
        Asset.yahoo_suffix == '.WA'
    ).all()
    apr_assets.extend(apr_assets_wa)
    
    for asset in apr_assets:
        print(f"Asset ID: {asset.id}")
        print(f"  • ISIN: {asset.isin}")
        print(f"  • Symbol: {asset.symbol}")
        print(f"  • Yahoo Ticker: {asset.yahoo_ticker}")
        print(f"  • Yahoo Suffix: {asset.yahoo_suffix}")
        print(f"  • Exchange: {asset.exchange}")
        print(f"  • MIC: {asset.mic}")
        print(f"  • Current Price: {asset.current_price} {asset.currency}")
        print(f"  • Name: {asset.name}")
        
        # Verificar holdings
        holdings = PortfolioHolding.query.filter_by(asset_id=asset.id).all()
        if holdings:
            for h in holdings:
                print(f"  • Holding: {h.quantity} unidades")
        print()
    
    # Buscar 0RI1
    print("2️⃣  BUSCANDO '0RI1':")
    print("-" * 80)
    ori1_assets = Asset.query.filter(
        Asset.symbol.like('%0RI1%')
    ).all()
    
    # También buscar por símbolos que empiecen con 0
    ori1_assets_0 = Asset.query.filter(
        Asset.symbol.like('0%')
    ).all()
    ori1_assets.extend(ori1_assets_0)
    
    for asset in ori1_assets:
        print(f"Asset ID: {asset.id}")
        print(f"  • ISIN: {asset.isin}")
        print(f"  • Symbol: {asset.symbol}")
        print(f"  • Yahoo Ticker: {asset.yahoo_ticker}")
        print(f"  • Yahoo Suffix: {asset.yahoo_suffix}")
        print(f"  • Exchange: {asset.exchange}")
        print(f"  • MIC: {asset.mic}")
        print(f"  • Current Price: {asset.current_price} {asset.currency}")
        print(f"  • Name: {asset.name}")
        
        # Verificar holdings
        holdings = PortfolioHolding.query.filter_by(asset_id=asset.id).all()
        if holdings:
            for h in holdings:
                print(f"  • Holding: {h.quantity} unidades")
        print()
    
    # Buscar assets con 654 unidades
    print("3️⃣  BUSCANDO ASSETS CON 654 UNIDADES:")
    print("-" * 80)
    holdings_654 = PortfolioHolding.query.filter_by(quantity=654).all()
    
    for holding in holdings_654:
        asset = holding.asset
        if asset:
            print(f"Asset ID: {asset.id}")
            print(f"  • ISIN: {asset.isin}")
            print(f"  • Symbol: {asset.symbol}")
            print(f"  • Yahoo Ticker: {asset.yahoo_ticker}")
            print(f"  • Current Price: {asset.current_price} {asset.currency}")
            print(f"  • Quantity: {holding.quantity}")
            print()
    
    # Buscar en AssetRegistry
    print("4️⃣  BUSCANDO EN ASSETREGISTRY:")
    print("-" * 80)
    
    apr_registry = AssetRegistry.query.filter(
        AssetRegistry.symbol.like('%APR%')
    ).all()
    
    ori1_registry = AssetRegistry.query.filter(
        AssetRegistry.symbol.like('%0RI1%')
    ).all()
    
    # También buscar por símbolos que empiecen con 0
    ori1_registry_0 = AssetRegistry.query.filter(
        AssetRegistry.symbol.like('0%')
    ).all()
    ori1_registry.extend(ori1_registry_0)
    
    if apr_registry:
        print("APR en AssetRegistry:")
        for r in apr_registry:
            print(f"  • ISIN: {r.isin}")
            print(f"    Symbol: {r.symbol}")
            print(f"    Yahoo Ticker: {r.yahoo_ticker}")
            print(f"    Yahoo Suffix: {r.yahoo_suffix}")
            print(f"    Exchange: {r.ibkr_exchange}")
            print(f"    MIC: {r.mic}")
            print()
    
    if ori1_registry:
        print("0RI1 en AssetRegistry:")
        for r in ori1_registry:
            print(f"  • ISIN: {r.isin}")
            print(f"    Symbol: {r.symbol}")
            print(f"    Yahoo Ticker: {r.yahoo_ticker}")
            print(f"    Yahoo Suffix: {r.yahoo_suffix}")
            print(f"    Exchange: {r.ibkr_exchange}")
            print(f"    MIC: {r.mic}")
            print()
    
    print("="*80)
    print("✅ BÚSQUEDA COMPLETADA")
    print("="*80 + "\n")

