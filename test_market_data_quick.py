"""
Test rápido de Market Data Services
"""
print("\n" + "="*60)
print("TEST RÁPIDO - MARKET DATA SERVICES")
print("="*60)

# Test 1: Mappers
print("\n1️⃣ Probando Mappers...")
try:
    from app.services.market_data.mappers import ExchangeMapper, YahooSuffixMapper, MICMapper
    
    print("   ✅ ExchangeMapper importado")
    print(f"      NDQ → {ExchangeMapper.degiro_to_unified('NDQ')}")
    print(f"      MAD → {ExchangeMapper.degiro_to_unified('MAD')}")
    
    print("   ✅ YahooSuffixMapper importado")
    print(f"      XMAD → '{YahooSuffixMapper.mic_to_yahoo_suffix('XMAD')}'")
    print(f"      XLON → '{YahooSuffixMapper.mic_to_yahoo_suffix('XLON')}'")
    print(f"      XNAS → '{YahooSuffixMapper.mic_to_yahoo_suffix('XNAS')}'")
    
    print("   ✅ MICMapper importado")
    print(f"      XNAS es US? {MICMapper.is_us_market('XNAS')}")
    print(f"      XHKG región: {MICMapper.get_region('XHKG')}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Providers
print("\n2️⃣ Probando Providers...")
try:
    from app.services.market_data.providers import OpenFIGIProvider, YahooFinanceProvider
    
    print("   ✅ OpenFIGIProvider importado")
    print("   ✅ YahooFinanceProvider importado")
    
    # Test Yahoo parse URL
    yahoo = YahooFinanceProvider()
    parsed = yahoo.parse_yahoo_url('https://es.finance.yahoo.com/quote/PSG.MC/')
    print(f"      URL parseada: {parsed}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: AssetEnricher
print("\n3️⃣ Probando AssetEnricher...")
try:
    from app.services.market_data import AssetEnricher
    
    print("   ✅ AssetEnricher importado")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Modelo Asset
print("\n4️⃣ Probando Modelo Asset...")
try:
    from app.models import Asset
    from app import db, create_app
    
    app = create_app()
    with app.app_context():
        # Verificar si hay assets en BD
        count = Asset.query.count()
        print(f"   ✅ Assets en BD: {count}")
        
        if count > 0:
            asset = Asset.query.first()
            print(f"      Ejemplo: {asset.symbol or asset.name}")
            print(f"      - MIC: {asset.mic or 'NULL'}")
            print(f"      - Yahoo Suffix: {asset.yahoo_suffix or 'NULL'}")
            print(f"      - Yahoo Ticker: {asset.yahoo_ticker or 'NULL'}")
        else:
            print("      ⚠️  No hay assets en la BD todavía")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("✅ TEST COMPLETADO")
print("="*60)
print("\n📝 PRÓXIMOS PASOS:")
print("   1. Revisar resultados")
print("   2. Continuar con TODOs 7-12 cuando estés listo")
print("   3. Ver ESTADO_IMPLEMENTACION_MARKET_DATA.md para detalles\n")

