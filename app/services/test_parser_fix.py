#!/usr/bin/env python3
"""
Script para probar que el parser corregido lee las monedas correctamente
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_transactions_parser import DeGiroTransactionsParser

# Probar el parser
parser = DeGiroTransactionsParser()
result = parser.parse('uploads/TransaccionesDegiro.csv')

print("\n" + "="*80)
print("TEST: PARSER CORREGIDO - VERIFICACIÓN DE MONEDAS")
print("="*80 + "\n")

print(f"📊 Total trades: {len(result['trades'])}\n")

# Buscar trades de los assets problemáticos
problem_assets = ['ANXIAN', 'CONSUN', 'GQG', 'EXCELLENCE', 'PAX GLOBAL']

print("🔍 VERIFICACIÓN DE MONEDAS EN TRADES:\n")

for asset_name in problem_assets:
    print(f"\n{asset_name}:")
    found = False
    for trade in result['trades']:
        if asset_name.lower() in trade['symbol'].lower():
            print(f"  ✅ Symbol: {trade['symbol']}")
            print(f"     Currency: '{trade['currency']}'")
            print(f"     Price: {trade['price']}")
            print(f"     Quantity: {trade['quantity']}")
            print(f"     Date: {trade['date']}")
            found = True
            break
    
    if not found:
        print(f"  ⚠️  No se encontró")

# Mostrar algunos ejemplos más
print("\n" + "="*80)
print("📋 PRIMEROS 5 TRADES:")
print("="*80 + "\n")

for i, trade in enumerate(result['trades'][:5], 1):
    print(f"{i}. {trade['symbol']}")
    print(f"   Type: {trade['transaction_type']}")
    print(f"   Currency: '{trade['currency']}'")
    print(f"   Price: {trade['price']} | Quantity: {trade['quantity']}")
    print(f"   Commission: {trade['commission']}")
    print()

