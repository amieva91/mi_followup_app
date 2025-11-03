#!/usr/bin/env python3
"""
Test usando la API directa de Yahoo Finance (sin yfinance)
"""

import requests
import time

def get_stock_data(symbol):
    """Obtener datos de un símbolo usando la API directa de Yahoo"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('chart', {}).get('error'):
                return None, f"Error API: {data['chart']['error']}"
            
            result = data['chart']['result'][0]
            meta = result['meta']
            
            return {
                'symbol': meta.get('symbol'),
                'currency': meta.get('currency'),
                'regularMarketPrice': meta.get('regularMarketPrice'),
                'previousClose': meta.get('chartPreviousClose'),
                'exchange': meta.get('exchangeName'),
                'instrumentType': meta.get('instrumentType'),
            }, None
        else:
            return None, f"HTTP {response.status_code}: {response.text[:100]}"
            
    except Exception as e:
        return None, str(e)

print("=" * 80)
print("🧪 TEST: API Directa de Yahoo Finance")
print("=" * 80)

test_symbols = ["AAPL", "ASTS", "SPR.WA", "9997.HK", "URC.TO", "NKR.OL", "HSBK", "9616.HK", "ZOMD", "DAT.WA"]

success = 0
failed = 0

for symbol in test_symbols:
    print(f"\n🔍 {symbol}...", end=" ")
    
    data, error = get_stock_data(symbol)
    
    if data:
        price = data.get('regularMarketPrice')
        currency = data.get('currency', '???')
        exchange = data.get('exchange', 'N/A')
        print(f"✅ {price} {currency} ({exchange})")
        success += 1
    else:
        print(f"❌ {error}")
        failed += 1
    
    time.sleep(0.3)  # Pequeña pausa

print("\n" + "=" * 80)
print("📊 RESUMEN:")
print(f"   ✅ Exitosos: {success}/{len(test_symbols)}")
print(f"   ❌ Fallidos: {failed}/{len(test_symbols)}")
print("=" * 80)

if success == len(test_symbols):
    print("\n🎉 ¡PERFECTO! Todos los precios se obtuvieron correctamente.")
    print("💡 Debemos usar la API directa en vez de yfinance.info")
elif success > len(test_symbols) // 2:
    print("\n✅ La mayoría funcionan. Algunos símbolos pueden ser inválidos.")
else:
    print("\n⚠️ Aún hay problemas. Puede ser rate limiting temporal.")

