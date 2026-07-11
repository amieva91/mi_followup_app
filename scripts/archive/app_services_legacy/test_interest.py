#!/usr/bin/env python3
"""
Script para probar el parsing de Intereses
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.ibkr_parser import IBKRParser

csv_file = 'uploads/U12722327_20230912_20240911.csv'

print("\n" + "="*80)
print("TEST: PARSING DE INTERESES (APALANCAMIENTO)")
print("="*80 + "\n")

parser = IBKRParser()
result = parser.parse(csv_file)

print(f"📊 FEES (Intereses) encontrados: {len(result['fees'])}\n")

for i, fee in enumerate(result['fees'], 1):
    print(f"{i}. {fee['date']} | {fee['amount']:.2f} {fee['currency']}")
    print(f"   {fee['description']}")
    print()

print("="*80)

