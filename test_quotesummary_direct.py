#!/usr/bin/env python3
"""
Test directo a quoteSummary API sin yfinance
Para obtener: sector, industry, precio
"""

import requests
import time

def get_asset_data(symbol):
    """
    Obtener sector, industry y precio de un símbolo
    usando la API directa de Yahoo Finance
    """
    
    # URL de quoteSummary (la que tiene sector, industry, etc.)
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    params = {
        'modules': 'price,assetProfile,summaryDetail'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'quoteSummary' not in data:
                return None, "No quoteSummary en respuesta"
            
            if data['quoteSummary'].get('error'):
                return None, f"Error API: {data['quoteSummary']['error']}"
            
            result_data = data['quoteSummary']['result']
            if not result_data:
                return None, "Sin resultados"
            
            # Extraer datos
            info = result_data[0]
            
            output = {
                'symbol': symbol,
            }
            
            # PRECIO (de 'price' module)
            if 'price' in info:
                price_data = info['price']
                output['current_price'] = price_data.get('regularMarketPrice', {}).get('raw')
                output['currency'] = price_data.get('currency')
            
            # SECTOR e INDUSTRY (de 'assetProfile' module)
            if 'assetProfile' in info:
                profile = info['assetProfile']
                output['sector'] = profile.get('sector')
                output['industry'] = profile.get('industry')
            
            return output, None
            
        elif response.status_code == 429:
            return None, "❌ Rate limit (429)"
        else:
            return None, f"HTTP {response.status_code}: {response.text[:100]}"
            
    except Exception as e:
        return None, f"Exception: {str(e)}"

print("=" * 100)
print("🧪 TEST: quoteSummary API directa (sin yfinance)")
print("=" * 100)
print("\n📊 Intentando obtener: Precio, Sector, Industry")
print("=" * 100)

# Probar con algunos símbolos
test_symbols = [
    "AAPL",      # Apple - US
    "ASTS",      # AST SpaceMobile - US
    "SPR.WA",    # Spyrosoft - Polonia
    "9997.HK",   # Hong Kong
    "URC.TO",    # Uranium Royalty - Canadá
]

success = 0
failed = 0
rate_limited = 0

for symbol in test_symbols:
    print(f"\n{'─' * 100}")
    print(f"🔍 Probando: {symbol}")
    print(f"{'─' * 100}")
    
    data, error = get_asset_data(symbol)
    
    if data:
        print(f"   ✅ ÉXITO")
        print(f"      💰 Precio:    {data.get('current_price')} {data.get('currency')}")
        print(f"      🏢 Sector:    {data.get('sector')}")
        print(f"      🏭 Industry:  {data.get('industry')}")
        success += 1
    else:
        print(f"   ❌ FALLÓ: {error}")
        if "429" in str(error):
            rate_limited += 1
        failed += 1
    
    # Pausa entre requests
    if symbol != test_symbols[-1]:
        print(f"   ⏳ Esperando 2s...")
        time.sleep(2)

print(f"\n{'=' * 100}")
print("📊 RESUMEN:")
print(f"   ✅ Exitosos:      {success}/{len(test_symbols)}")
print(f"   ❌ Fallidos:      {failed}/{len(test_symbols)}")
print(f"   🚫 Rate limited:  {rate_limited}/{len(test_symbols)}")
print("=" * 100)

if success > 0:
    print("\n🎉 ¡FUNCIONA! quoteSummary responde sin yfinance")
    print("💡 Podemos integrar esto en el PriceUpdater")
elif rate_limited > 0:
    print("\n⚠️ Bloqueado por rate limit (429)")
    print("💡 Necesitamos esperar o usar otra estrategia")
else:
    print("\n❌ No funciona con esta configuración")
    print("💡 Necesitamos otra solución (API alternativa, proxies, etc.)")

