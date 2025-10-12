#!/usr/bin/env python3
"""
Script para probar el parsing de Depósitos y Retiros
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.ibkr_parser import IBKRParser

csv_file = 'uploads/U12722327_20240912_20250911.csv'

print("\n" + "="*80)
print("TEST: PARSING DE DEPÓSITOS Y RETIROS")
print("="*80 + "\n")

parser = IBKRParser()
result = parser.parse(csv_file)

print(f"📊 DEPÓSITOS encontrados: {len(result['deposits'])}\n")
for i, deposit in enumerate(result['deposits'], 1):
    print(f"{i}. {deposit['date']} | {deposit['amount']} {deposit['currency']}")
    print(f"   {deposit['description']}")
    print()

print(f"📊 RETIROS encontrados: {len(result['withdrawals'])}\n")
for i, withdrawal in enumerate(result['withdrawals'], 1):
    print(f"{i}. {withdrawal['date']} | -{withdrawal['amount']} {withdrawal['currency']}")
    print(f"   {withdrawal['description']}")
    print()

print("="*80)

