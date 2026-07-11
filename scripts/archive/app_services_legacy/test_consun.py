#!/usr/bin/env python3
"""Script para verificar CONSUN PHARMACEUTICAL GROUP LTD"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test():
    csv_path = 'uploads/Degiro.csv'
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    # Buscar CONSUN
    consun = [d for d in data['dividends'] if 'CONSUN' in d.get('symbol', '')]
    
    if consun:
        div = consun[0]
        
        print("=" * 80)
        print("DIVIDENDO DE CONSUN PHARMACEUTICAL GROUP LTD")
        print("=" * 80)
        print()
        print(f"📅 Fecha: {div.get('date')}")
        print()
        print(f"💰 Dividendo:")
        print(f"   amount: {div.get('amount')} {div.get('currency')}")
        if 'amount_original' in div:
            print(f"   amount_original: {div.get('amount_original')} {div.get('currency_original')}")
        print()
        print(f"💸 Retención:")
        print(f"   tax: {div.get('tax')}")
        print(f"   tax_eur: {div.get('tax_eur')} EUR")
        print()
        print("=" * 80)
        print()
        print("✅ ESPERADO (según CSV):")
        print("   - Dividendo: 2970.00 HKD (22/09/2025)")
        print("   - Retirada: 2970.00 HKD con tasa 91.888")
        print("   - Ingreso: 323.22 EUR (23/09/2025)")
        print("   - Relación: 2970.00 / exchange_rate ≈ 323.22 EUR")
        print()
        print("   Si exchange_rate = 91.888 → 2970 / 91.888 = 32.32 EUR ❌")
        print("   Si exchange_rate = 9.1888 → 2970 / 9.1888 = 323.21 EUR ✅")
    else:
        print("❌ No se encontró CONSUN en los dividendos")

if __name__ == '__main__':
    test()

