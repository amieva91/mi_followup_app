#!/usr/bin/env python3
"""
Verificar QUÉ está devolviendo exactamente Yahoo Finance
"""

import requests
import time

print("=" * 80)
print("🔍 VERIFICANDO RESPUESTA DE YAHOO FINANCE")
print("=" * 80)

# URLs a probar
urls = [
    ("Chart API", "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"),
    ("Quote API", "https://query2.finance.yahoo.com/v7/finance/quote?symbols=AAPL"),
    ("Crumb", "https://query1.finance.yahoo.com/v1/test/getcrumb"),
]

for name, url in urls:
    print(f"\n📊 {name}")
    print(f"   URL: {url}")
    print("-" * 80)
    
    try:
        # Sin headers especiales
        response = requests.get(url, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   Content-Length: {len(response.content)} bytes")
        print(f"   Primeros 500 caracteres:")
        print(f"   {response.text[:500]}")
        
        if response.status_code == 200:
            print(f"   ✅ Respuesta exitosa")
        elif response.status_code == 429:
            print(f"   ⚠️ Rate limit (429)")
        else:
            print(f"   ❌ Error: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout - Yahoo Finance no responde")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Error de conexión - Problema de red")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    time.sleep(2)

# Test con User-Agent
print("\n" + "=" * 80)
print("📊 PRUEBA CON USER-AGENT (simulando navegador)")
print("=" * 80)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
    response = requests.get(url, headers=headers, timeout=10)
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Primeros 200 caracteres: {response.text[:200]}")
    
    if response.status_code == 200:
        data = response.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        print(f"   ✅ PRECIO OBTENIDO: ${price:.2f}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 80)
print("✅ DIAGNÓSTICO COMPLETADO")
print("=" * 80)

