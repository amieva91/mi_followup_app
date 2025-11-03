#!/usr/bin/env python3
"""
Script de diagnóstico para Yahoo Finance
Prueba diferentes métodos y símbolos para identificar el problema
"""

import yfinance as yf
import requests
import time
import logging

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 80)
print("🔬 DIAGNÓSTICO DE YAHOO FINANCE")
print("=" * 80)

# ============================================================================
# TEST 1: Símbolo simple y común (AAPL)
# ============================================================================
print("\n📊 TEST 1: Probando AAPL (símbolo más común)")
print("-" * 80)
try:
    ticker = yf.Ticker("AAPL")
    print("✓ Ticker object creado")
    
    # Intentar obtener info
    info = ticker.info
    print(f"✅ INFO OBTENIDA:")
    print(f"   - Symbol: {info.get('symbol', 'N/A')}")
    print(f"   - Name: {info.get('longName', 'N/A')}")
    print(f"   - Current Price: {info.get('currentPrice', 'N/A')}")
    print(f"   - Currency: {info.get('currency', 'N/A')}")
    print(f"   - Keys disponibles: {len(info.keys())}")
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

time.sleep(3)

# ============================================================================
# TEST 2: Método alternativo - history() en vez de info
# ============================================================================
print("\n📊 TEST 2: Probando AAPL con history() (más confiable)")
print("-" * 80)
try:
    ticker = yf.Ticker("AAPL")
    hist = ticker.history(period="5d")
    
    if not hist.empty:
        last_close = hist['Close'].iloc[-1]
        print(f"✅ HISTORY OBTENIDO:")
        print(f"   - Último precio cierre: ${last_close:.2f}")
        print(f"   - Datos disponibles: {len(hist)} días")
        print(f"   - Columnas: {list(hist.columns)}")
    else:
        print("⚠️ History vacío")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

time.sleep(3)

# ============================================================================
# TEST 3: Uno de los símbolos del usuario (ASTS)
# ============================================================================
print("\n📊 TEST 3: Probando ASTS (uno de tus activos)")
print("-" * 80)
try:
    ticker = yf.Ticker("ASTS")
    hist = ticker.history(period="5d")
    
    if not hist.empty:
        last_close = hist['Close'].iloc[-1]
        print(f"✅ HISTORY OBTENIDO:")
        print(f"   - Último precio cierre: ${last_close:.2f}")
        print(f"   - Datos disponibles: {len(hist)} días")
    else:
        print("⚠️ History vacío")
        
    # Intentar info también
    print("\n   Intentando obtener .info para ASTS...")
    info = ticker.info
    print(f"   - Symbol: {info.get('symbol', 'N/A')}")
    print(f"   - Current Price: {info.get('currentPrice', 'N/A')}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")

time.sleep(3)

# ============================================================================
# TEST 4: Request directo a Yahoo Finance (sin yfinance)
# ============================================================================
print("\n📊 TEST 4: Request HTTP directo a Yahoo Finance")
print("-" * 80)
try:
    url = "https://query2.finance.yahoo.com/v8/finance/chart/AAPL"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    print(f"   - Status Code: {response.status_code}")
    print(f"   - Content Length: {len(response.content)} bytes")
    
    if response.status_code == 200:
        data = response.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        print(f"✅ Precio obtenido directamente: ${price:.2f}")
    else:
        print(f"⚠️ Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")

time.sleep(3)

# ============================================================================
# TEST 5: Verificar conexión a internet
# ============================================================================
print("\n📊 TEST 5: Verificando conectividad general")
print("-" * 80)
test_urls = [
    "https://www.google.com",
    "https://finance.yahoo.com",
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com"
]

for url in test_urls:
    try:
        response = requests.get(url, timeout=5)
        print(f"✅ {url}: {response.status_code}")
    except Exception as e:
        print(f"❌ {url}: {e}")

# ============================================================================
# TEST 6: Verificar yfinance está usando cache corrupto
# ============================================================================
print("\n📊 TEST 6: Limpiando cache de yfinance")
print("-" * 80)
try:
    import os
    cache_dir = os.path.expanduser("~/.cache/py-yfinance")
    if os.path.exists(cache_dir):
        import shutil
        shutil.rmtree(cache_dir)
        print(f"✅ Cache eliminado: {cache_dir}")
    else:
        print(f"ℹ️ No hay cache en: {cache_dir}")
except Exception as e:
    print(f"⚠️ No se pudo limpiar cache: {e}")

print("\n" + "=" * 80)
print("🏁 DIAGNÓSTICO COMPLETADO")
print("=" * 80)
print("\nSi algún test funcionó, el problema es la configuración del servicio.")
print("Si TODOS fallaron, el problema puede ser de red/firewall/proxy.")

