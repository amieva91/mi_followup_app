#!/usr/bin/env python3
"""Script para verificar los datos completos de GQG"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test():
    csv_path = 'uploads/Degiro.csv'
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    # Buscar el dividendo más reciente de GQG
    gqg_divs = [d for d in data['dividends'] if 'GQG' in d.get('symbol', '')]
    
    if gqg_divs:
        div = gqg_divs[0]  # El más reciente (29-09-2025)
        
        print("=" * 80)
        print("DIVIDENDO MÁS RECIENTE DE GQG PARTNERS CDI")
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
        print(f"   tax: {div.get('tax')} {div.get('currency_original', div.get('currency'))}")
        print(f"   tax_eur: {div.get('tax_eur')} EUR")
        print()
        print("=" * 80)
        print()
        print("✅ ESPERADO:")
        print("   - Dividendo: 72.64 EUR (del 'Ingreso Cambio de Divisa')")
        print("   - Dividendo original: 152.74 AUD")
        print("   - Retención: 22.91 AUD")
        print("   - Retención EUR: 12.82 EUR (22.91 / 1.7873)")

if __name__ == '__main__':
    test()

