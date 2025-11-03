#!/usr/bin/env python3
"""
Limpia el cache corrupto de yfinance y prueba con método alternativo
"""

import os
import shutil
import yfinance as yf

print("=" * 80)
print("🔧 LIMPIANDO CACHE CORRUPTO DE YFINANCE")
print("=" * 80)

# 1. Limpiar todos los caches posibles
cache_locations = [
    os.path.expanduser("~/.cache/py-yfinance"),
    os.path.expanduser("~/.yfinance"),
    "/tmp/yfinance_cache",
]

for cache_dir in cache_locations:
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print(f"✅ Cache eliminado: {cache_dir}")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar {cache_dir}: {e}")
    else:
        print(f"ℹ️ No existe: {cache_dir}")

# 2. Buscar y eliminar base de datos de cookies de peewee
import glob
cookie_dbs = glob.glob(os.path.expanduser("~/.cache/**/*cookie*"), recursive=True)
cookie_dbs.extend(glob.glob("/tmp/**/*cookie*", recursive=True))

for db_file in cookie_dbs:
    if os.path.isfile(db_file):
        try:
            os.remove(db_file)
            print(f"✅ DB de cookies eliminada: {db_file}")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar {db_file}: {e}")

print("\n" + "=" * 80)
print("📊 PROBANDO CON MÉTODO ALTERNATIVO (history en vez de info)")
print("=" * 80)

# 3. Probar con history() que es más confiable y no usa quoteSummary
test_symbols = ["AAPL", "ASTS", "SPR.WA"]

for symbol in test_symbols:
    print(f"\n🔍 Probando {symbol}...")
    try:
        ticker = yf.Ticker(symbol)
        
        # Usar history() en vez de info
        hist = ticker.history(period="1d")
        
        if not hist.empty:
            last_price = hist['Close'].iloc[-1]
            print(f"   ✅ Precio obtenido: ${last_price:.2f}")
        else:
            print(f"   ⚠️ Sin datos históricos")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 80)
print("✅ LIMPIEZA COMPLETADA")
print("=" * 80)
print("\n💡 RECOMENDACIÓN: Espera 2-3 minutos antes de hacer más requests")
print("   para que Yahoo Finance 'olvide' la IP temporal.")

