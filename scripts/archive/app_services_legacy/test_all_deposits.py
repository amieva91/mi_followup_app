#!/usr/bin/env python3
"""
Script para probar depósitos y retiros en todos los CSVs
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.ibkr_parser import IBKRParser

csv_files = [
    'uploads/U12722327_20230912_20240911.csv',
    'uploads/U12722327_20240912_20250911.csv',
]

print("\n" + "="*80)
print("TEST: DEPÓSITOS Y RETIROS EN TODOS LOS CSVs")
print("="*80 + "\n")

total_deposits = 0
total_withdrawals = 0

for csv_file in csv_files:
    if not os.path.exists(csv_file):
        continue
    
    print(f"📄 {os.path.basename(csv_file)}")
    print("-" * 80)
    
    parser = IBKRParser()
    result = parser.parse(csv_file)
    
    deposits = result['deposits']
    withdrawals = result['withdrawals']
    
    total_deposits += len(deposits)
    total_withdrawals += len(withdrawals)
    
    print(f"  Depósitos: {len(deposits)}")
    for dep in deposits[:3]:  # Mostrar solo los primeros 3
        print(f"    + {dep['amount']} {dep['currency']} | {dep['date']} | {dep['description'][:50]}")
    
    print(f"  Retiros: {len(withdrawals)}")
    for wit in withdrawals[:3]:  # Mostrar solo los primeros 3
        print(f"    - {wit['amount']} {wit['currency']} | {wit['date']} | {wit['description'][:50]}")
    
    print()

print("="*80)
print(f"✅ TOTAL: {total_deposits} depósitos, {total_withdrawals} retiros")
print("="*80 + "\n")

