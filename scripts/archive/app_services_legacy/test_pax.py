#!/usr/bin/env python3
"""Script para verificar PAX GLOBAL TECHNOLOGY LTD"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test():
    csv_path = 'uploads/Degiro.csv'
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    # Buscar PAX GLOBAL
    pax = [d for d in data['dividends'] if 'PAX GLOBAL' in d.get('symbol', '')]
    
    print("=" * 80)
    print("DIVIDENDOS DE PAX GLOBAL TECHNOLOGY LTD")
    print("=" * 80)
    print()
    
    if pax:
        for i, div in enumerate(pax, 1):
            print(f"--- Dividendo #{i} ---")
            print(f"📅 Fecha: {div.get('date')}")
            print(f"💰 Dividendo:")
            print(f"   amount: {div.get('amount')} {div.get('currency')}")
            if 'amount_original' in div:
                print(f"   amount_original: {div.get('amount_original')} {div.get('currency_original')}")
            print(f"💸 Retención:")
            print(f"   tax: {div.get('tax')}")
            print(f"   tax_eur: {div.get('tax_eur')} EUR")
            print()
    else:
        print("❌ No se encontró PAX GLOBAL en los dividendos")
    
    print("=" * 80)
    print()
    print("✅ ESPERADO (según CSV del 26/09/2025):")
    print("   - Dividendo: 1500.00 HKD (26/09/2025)")
    print("   - SIN retención (tax = 0)")
    print("   - Retirada: 1500.00 HKD con tasa 91.302 (27/09/2025)")
    print("   - Ingreso: 164.29 EUR (27/09/2025)")
    print("   - Relación: 1500.00 / 91.302 = 16.43 EUR ❌")
    print("   - Relación: 1500.00 / 9.1302 = 164.28 EUR ✅")

if __name__ == '__main__':
    test()

