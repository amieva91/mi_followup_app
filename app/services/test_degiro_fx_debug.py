#!/usr/bin/env python3
"""Debug FX matching"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser
from decimal import Decimal

parser = DeGiroParser()
result = parser.parse('uploads/Degiro.csv')

print("=" * 80)
print("DEBUG: FX MATCHING")
print("=" * 80)

# Revisar el primer dividendo que no es EUR
first_non_eur = None
for div in result['dividends']:
    if div['currency'] != 'EUR':
        first_non_eur = div
        break

if first_non_eur:
    print(f"\n💰 DIVIDENDO NO-EUR:")
    print(f"   Symbol: {first_non_eur['symbol']}")
    print(f"   Amount: {first_non_eur['amount']} {first_non_eur['currency']}")
    print(f"   Date: {first_non_eur['date']}")
    
    # Buscar FX Withdrawal que coincida
    amount = Decimal(str(first_non_eur['amount']))
    currency = first_non_eur['currency']
    
    print(f"\n📤 BUSCANDO RETIRADA CON: {amount} {currency}")
    print(f"\n🔍 FX WITHDRAWALS DISPONIBLES ({len(parser.fx_withdrawals)}):")
    for i, fx_w in enumerate(parser.fx_withdrawals[:10]):
        print(f"   {i+1}. {fx_w['amount']} {fx_w['currency']} | Fecha: {fx_w['date']}")
    
    matched = None
    for fx_w in parser.fx_withdrawals:
        if (abs(fx_w['amount'] - abs(amount)) < Decimal('0.01') and 
            fx_w['currency'] == currency):
            matched = fx_w
            break
    
    if matched:
        print(f"\n✅ ENCONTRADA RETIRADA: {matched['amount']} {matched['currency']} | {matched['date']}")
        print(f"\n📥 FX DEPOSITS DISPONIBLES ({len(parser.fx_deposits)}):")
        for i, fx_d in enumerate(parser.fx_deposits[:10]):
            print(f"   {i+1}. {fx_d['amount']} {fx_d['currency']} | Fecha: {fx_d['date']}")
    else:
        print(f"\n❌ NO SE ENCONTRÓ RETIRADA QUE COINCIDA")

print("\n" + "=" * 80)

