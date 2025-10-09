#!/usr/bin/env python3
"""Script para verificar el dividendo específico de PAX GLOBAL del 26/09/2025"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser
from decimal import Decimal

def test():
    csv_path = 'uploads/Degiro.csv'
    parser = DeGiroParser()
    
    print("=" * 80)
    print("DEBUGGING PAX GLOBAL 26/09/2025")
    print("=" * 80)
    
    # Parsear
    data = parser.parse(csv_path)
    
    # Buscar en dividend_fx_map antes de consolidar
    print("\n🔍 Buscando PAX GLOBAL en dividend_fx_map:")
    for key, value in parser.dividend_fx_map.items():
        if 'PAX GLOBAL' in key and '1500' in key:
            print(f"\n  Key: {key}")
            div_data = value.get('dividend', {})
            print(f"  Symbol: {div_data.get('symbol')}")
            print(f"  Date: {div_data.get('date')}")
            print(f"  Amount: {div_data.get('amount_original')}")
            print(f"  Currency: {div_data.get('currency_original')}")
            print(f"  Tax: {div_data.get('tax', Decimal('0'))}")
    
    # Buscar en fx_withdrawals
    print("\n🔍 Buscando FX withdrawal de 1500 HKD:")
    for i, fx_w in enumerate(parser.fx_withdrawals):
        if fx_w['amount'] == Decimal('1500.00') and fx_w['currency'] == 'HKD':
            print(f"\n  FX Withdrawal #{i+1}:")
            print(f"    Amount: {fx_w['amount']} {fx_w['currency']}")
            print(f"    Date: {fx_w['date']}")
            print(f"    Exchange rate: {fx_w.get('exchange_rate')}")
    
    # Buscar en fx_deposits
    print("\n🔍 Buscando FX deposit de ~164 EUR:")
    for i, fx_d in enumerate(parser.fx_deposits):
        if abs(fx_d['amount'] - Decimal('164.29')) < Decimal('1'):
            print(f"\n  FX Deposit #{i+1}:")
            print(f"    Amount: {fx_d['amount']} EUR")
            print(f"    Date: {fx_d['date']}")
    
    # Buscar en dividendos finales
    print("\n🔍 Buscando PAX GLOBAL en dividendos finales:")
    pax = [d for d in data['dividends'] if 'PAX GLOBAL' in d.get('symbol', '')]
    pax_sept = [d for d in pax if '2025-09-26' in d.get('date', '') or '2025-09-25' in d.get('date', '')]
    
    if pax_sept:
        for div in pax_sept:
            print(f"\n  ✅ ENCONTRADO:")
            print(f"    Fecha: {div.get('date')}")
            print(f"    Amount: {div.get('amount')} {div.get('currency')}")
            print(f"    Amount original: {div.get('amount_original')} {div.get('currency_original')}")
    else:
        print("\n  ❌ NO ENCONTRADO en dividendos de septiembre 2025")
        
    print("\n" + "=" * 80)

if __name__ == '__main__':
    test()

