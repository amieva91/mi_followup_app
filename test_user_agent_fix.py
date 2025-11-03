#!/usr/bin/env python3
"""
Test rápido de la solución del User-Agent
"""

import yfinance as yf
import requests

print("=" * 80)
print("🧪 TEST: User-Agent configurado en yfinance")
print("=" * 80)

# Configurar User-Agent
yf.session = requests.Session()
yf.session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

print("\n✅ User-Agent configurado")
print(f"   Headers: {yf.session.headers}")

# Probar con símbolos del usuario
test_symbols = ["AAPL", "ASTS", "SPR.WA", "9997.HK", "URC.TO"]

print("\n" + "-" * 80)
print("📊 PROBANDO ACTUALIZACIÓN DE PRECIOS")
print("-" * 80)

success = 0
failed = 0

for symbol in test_symbols:
    print(f"\n🔍 {symbol}...", end=" ")
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        price = info.get('regularMarketPrice') or info.get('currentPrice')
        
        if price:
            currency = info.get('currency', '???')
            name = info.get('shortName') or info.get('longName', 'N/A')
            print(f"✅ {price} {currency} - {name}")
            success += 1
        else:
            print(f"⚠️ Sin precio")
            failed += 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        failed += 1

print("\n" + "=" * 80)
print("📊 RESUMEN:")
print(f"   ✅ Exitosos: {success}/{len(test_symbols)}")
print(f"   ❌ Fallidos: {failed}/{len(test_symbols)}")
print("=" * 80)

if success > 0:
    print("\n🎉 ¡FUNCIONA! El User-Agent soluciona el problema.")
else:
    print("\n❌ Aún hay problemas. Puede necesitar más tiempo de espera.")

