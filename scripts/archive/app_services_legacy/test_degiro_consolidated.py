#!/usr/bin/env python3
"""Test consolidación de dividendos con FX y retención"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

parser = DeGiroParser()
result = parser.parse('uploads/Degiro.csv')

print("=" * 80)
print("TEST: Parser DeGiro - Consolidación de Dividendos")
print("=" * 80)

print(f"\n📊 RESULTADO:")
print(f"   Trades: {len(result.get('trades', []))}")
print(f"   Dividends: {len(result.get('dividends', []))}")
print(f"   Fees: {len(result.get('fees', []))}")
print(f"   Deposits: {len(result.get('deposits', []))}")
print(f"   Withdrawals: {len(result.get('withdrawals', []))}")

print(f"\n💰 PRIMEROS 10 DIVIDENDOS (consolidados con EUR + tax):")
for div in result['dividends'][:10]:
    symbol = div.get('symbol', 'N/A')[:40]
    amount = div.get('amount', 0)
    currency = div.get('currency', 'EUR')
    tax = div.get('tax', 0)
    date = div.get('date', 'N/A')
    print(f"   • {symbol:<40} | {amount:>10.2f} {currency} | Tax: {tax:>6.2f} | {date}")

print(f"\n💸 COMISIONES (incluyendo apalancamiento):")
for fee in result['fees'][:10]:
    desc = fee.get('description', 'N/A')[:50]
    amount = fee.get('amount', 0)
    currency = fee.get('currency', 'EUR')
    date = fee.get('date', 'N/A')
    print(f"   • {desc:<50} | {amount:>8.2f} {currency} | {date}")

print(f"\n📥 DEPÓSITOS:")
for dep in result['deposits'][:5]:
    desc = dep.get('description', 'N/A')[:50]
    amount = dep.get('amount', 0)
    currency = dep.get('currency', 'EUR')
    date = dep.get('date', 'N/A')
    print(f"   • {desc:<50} | {amount:>10.2f} {currency} | {date}")

print(f"\n📤 RETIROS:")
for wit in result['withdrawals'][:5]:
    desc = wit.get('description', 'N/A')[:50]
    amount = wit.get('amount', 0)
    currency = wit.get('currency', 'EUR')
    date = wit.get('date', 'N/A')
    print(f"   • {desc:<50} | {amount:>10.2f} {currency} | {date}")

print("\n" + "=" * 80)

