#!/usr/bin/env python3
"""Test parser de dividendos de DeGiro"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

parser = DeGiroParser()
result = parser.parse('uploads/Degiro.csv')

print("=" * 80)
print("TEST: Parser DeGiro - Estado de Cuenta")
print("=" * 80)

print(f"\n📊 RESULTADO:")
print(f"   Trades: {len(result.get('trades', []))}")
print(f"   Dividends: {len(result.get('dividends', []))}")
print(f"   Fees: {len(result.get('fees', []))}")
print(f"   Deposits: {len(result.get('deposits', []))}")
print(f"   FX: {len(result.get('fx_transactions', []))}")

if result.get('dividends'):
    print(f"\n💰 DIVIDENDOS ENCONTRADOS:")
    for div in result['dividends'][:10]:
        print(f"   • {div.get('symbol', 'N/A')[:40]:<40} | {div.get('amount'):>10.2f} {div.get('currency')} | {div.get('date')}")
else:
    print(f"\n⚠️  NO SE ENCONTRARON DIVIDENDOS")
    print(f"   Verifica el formato del CSV...")

print("\n" + "=" * 80)

