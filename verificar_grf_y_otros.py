"""
Script para verificar GRF y otros assets con posibles problemas
"""
from app import create_app, db
from app.models import Asset, AssetRegistry, PortfolioHolding

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔍 VERIFICANDO GRF Y OTROS ASSETS")
    print("="*80 + "\n")
    
    # Buscar GRF
    print("1️⃣  VERIFICANDO GRF:")
    print("-" * 80)
    
    grf_assets = Asset.query.filter_by(symbol='GRF').all()
    for asset in grf_assets:
        print(f"Asset ID: {asset.id}")
        print(f"  • ISIN: {asset.isin}")
        print(f"  • Symbol: {asset.symbol}")
        print(f"  • Yahoo Ticker: {asset.yahoo_ticker}")
        print(f"  • Yahoo Suffix: {asset.yahoo_suffix}")
        print(f"  • Exchange: {asset.exchange}")
        print(f"  • MIC: {asset.mic}")
        print(f"  • Current Price: {asset.current_price} {asset.currency}")
        print(f"  • Last Update: {asset.last_price_update}")
        
        holdings = PortfolioHolding.query.filter_by(asset_id=asset.id).all()
        if holdings:
            for h in holdings:
                print(f"  • Holding: {h.quantity} unidades")
        print()
    
    # Buscar en AssetRegistry
    grf_registry = AssetRegistry.query.filter_by(symbol='GRF').all()
    if grf_registry:
        print("AssetRegistry:")
        for r in grf_registry:
            print(f"  • ISIN: {r.isin}")
            print(f"    Symbol: {r.symbol}")
            print(f"    Yahoo Ticker: {r.yahoo_ticker}")
            print(f"    Yahoo Suffix: {r.yahoo_suffix}")
            print(f"    Exchange: {r.ibkr_exchange}")
            print(f"    MIC: {r.mic}")
            print()
    
    # Buscar otros assets con posibles problemas
    print("2️⃣  BUSCANDO ASSETS CON PRECIOS DIFERENTES O PROBLEMAS:")
    print("-" * 80)
    
    # Assets con holdings que pueden tener problemas
    holdings = PortfolioHolding.query.filter(PortfolioHolding.quantity > 0).all()
    
    problematic = []
    for holding in holdings:
        asset = holding.asset
        if asset:
            issues = []
            
            # Sin precio
            if not asset.current_price:
                issues.append('Sin precio')
            
            # Ticker sin sufijo pero debería tenerlo
            if asset.yahoo_ticker and '.' not in asset.yahoo_ticker and asset.yahoo_suffix:
                issues.append('Ticker mal construido')
            
            # MIC y suffix inconsistentes
            if asset.mic and asset.yahoo_suffix:
                # Verificar si el suffix corresponde al MIC
                mic_to_suffix = {
                    'XWAR': '.WA',
                    'XLON': '.L',
                    'XMAD': '.MC',
                    'XTSX': '.V',
                    'XTSE': '.TO',
                }
                expected_suffix = mic_to_suffix.get(asset.mic)
                if expected_suffix and asset.yahoo_suffix != expected_suffix:
                    issues.append(f'MIC/Suffix inconsistente (MIC={asset.mic}, Suffix={asset.yahoo_suffix})')
            
            if issues:
                problematic.append({
                    'asset': asset,
                    'holding': holding,
                    'issues': issues
                })
    
    if problematic:
        print(f"Total assets problemáticos: {len(problematic)}")
        for p in problematic[:10]:
            asset = p['asset']
            print(f"\n  • {asset.symbol} ({asset.isin[:12] if asset.isin else 'N/A'}...):")
            print(f"    Problemas: {', '.join(p['issues'])}")
            print(f"    Ticker: {asset.yahoo_ticker}")
            print(f"    Suffix: {asset.yahoo_suffix}")
            print(f"    MIC: {asset.mic}")
            print(f"    Precio: {asset.current_price} {asset.currency}")
            print(f"    Cantidad: {p['holding'].quantity}")
    else:
        print("✅ No se encontraron problemas obvios")
    
    print("\n" + "="*80)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("="*80 + "\n")

