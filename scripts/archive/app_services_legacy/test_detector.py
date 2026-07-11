#!/usr/bin/env python3
"""Test detector para ambos formatos de DeGiro"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.csv_detector import CSVDetector

print("=" * 80)
print("TEST: Detector de Formatos DeGiro")
print("=" * 80)

# Test 1: Estado de Cuenta
format1 = CSVDetector.detect_format_from_file('uploads/Degiro.csv')
print(f"\n1. Degiro.csv (Estado de Cuenta)")
print(f"   Formato detectado: {format1}")
print(f"   ✅ CORRECTO" if format1 == 'DEGIRO_ACCOUNT' else f"   ❌ INCORRECTO (esperado: DEGIRO_ACCOUNT)")

# Test 2: Transacciones
format2 = CSVDetector.detect_format_from_file('uploads/TransaccionesDegiro.csv')
print(f"\n2. TransaccionesDegiro.csv (Transacciones)")
print(f"   Formato detectado: {format2}")
print(f"   ✅ CORRECTO" if format2 == 'DEGIRO_TRANSACTIONS' else f"   ❌ INCORRECTO (esperado: DEGIRO_TRANSACTIONS)")

# Test 3: Parsear con el parser correcto
print(f"\n3. Probar parser de Transacciones:")
try:
    parser_class = CSVDetector.get_parser_class(format2)
    parser = parser_class()
    result = parser.parse('uploads/TransaccionesDegiro.csv')
    
    print(f"   Broker: {result['broker']}")
    print(f"   Trades: {len(result['trades'])}")
    print(f"   Holdings: {len(result['holdings'])}")
    print(f"   ✅ Parser funciona correctamente")
    
    # Mostrar holdings
    print(f"\n   Holdings detectados:")
    for h in sorted(result['holdings'], key=lambda x: x['symbol'])[:10]:
        print(f"      • {h['symbol'][:40]:<40} | Qty: {h['quantity']:>8} | ISIN: {h['isin']}")
    
    if len(result['holdings']) > 10:
        print(f"      ... y {len(result['holdings']) - 10} más")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

