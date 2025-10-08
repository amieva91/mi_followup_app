#!/usr/bin/env python3
"""Script para verificar que se extrae correctamente tax_eur de dividendos DeGiro"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test_tax_eur():
    csv_path = 'uploads/Degiro.csv'
    
    print("=" * 80)
    print("VERIFICACIÓN DE TAX_EUR EN DIVIDENDOS DEGIRO")
    print("=" * 80)
    
    # Parsear directamente con DeGiroParser (Estado de Cuenta)
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    print(f"\n📊 Total dividendos: {len(data['dividends'])}")
    print("\n" + "=" * 80)
    
    # Filtrar dividendos con tax > 0
    dividends_with_tax = [d for d in data['dividends'] if d.get('tax', 0) > 0]
    
    print(f"💰 Dividendos con retención fiscal: {len(dividends_with_tax)}\n")
    
    for div in dividends_with_tax:
        symbol = div.get('symbol', 'N/A')
        date = div.get('date', 'N/A')
        amount = div.get('amount', 0)
        currency = div.get('currency', 'N/A')
        tax = div.get('tax', 0)
        tax_eur = div.get('tax_eur', 0)
        
        print(f"📌 {symbol} ({date})")
        print(f"   Dividendo: {amount:.2f} {currency}")
        print(f"   Retención: {tax:.2f} {currency}", end="")
        
        if tax_eur > 0:
            print(f" → {tax_eur:.2f} EUR ✅")
        else:
            if currency == 'EUR':
                print(" (ya en EUR) ✅")
            else:
                print(" ❌ NO SE CALCULÓ EUR")
        print()
    
    # Casos específicos
    print("=" * 80)
    print("🔍 CASOS ESPECÍFICOS:")
    print("=" * 80)
    
    # GQG PARTNERS CDI (AUD)
    gqg = [d for d in dividends_with_tax if 'GQG' in d.get('symbol', '')]
    if gqg:
        print("\n✅ GQG PARTNERS CDI (AUD):")
        for d in gqg:
            print(f"   Retención: {d.get('tax', 0):.2f} {d.get('currency')} → {d.get('tax_eur', 0):.2f} EUR")
    
    # MANULIFE (HKD)
    manulife = [d for d in dividends_with_tax if 'MANULIFE' in d.get('symbol', '')]
    if manulife:
        print("\n✅ MANULIFE FINANCIAL CORP (HKD):")
        for d in manulife:
            print(f"   Retención: {d.get('tax', 0):.2f} {d.get('currency')} → {d.get('tax_eur', 0):.2f} EUR")
    
    # GRIFOLS (EUR)
    grifols = [d for d in dividends_with_tax if 'GRIFOLS' in d.get('symbol', '')]
    if grifols:
        print("\n✅ GRIFOLS SA (EUR - ya en moneda base):")
        for d in grifols:
            print(f"   Retención: {d.get('tax', 0):.2f} {d.get('currency')} (tax_eur no aplica)")

if __name__ == '__main__':
    test_tax_eur()

