#!/usr/bin/env python3
"""Script para debuggear la consolidación con logging detallado"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser
from decimal import Decimal
from datetime import datetime

# Monkeypatch para agregar logging
original_consolidate = DeGiroParser._consolidate_dividends

def logged_consolidate(self):
    print("\n" + "=" * 80)
    print("CONSOLIDANDO DIVIDENDOS")
    print("=" * 80)
    
    print(f"\n📊 Total dividend_fx_map entries: {len(self.dividend_fx_map)}")
    print(f"📊 Total fx_withdrawals: {len(self.fx_withdrawals)}")
    print(f"📊 Total fx_deposits: {len(self.fx_deposits)}")
    
    # Buscar GQG específicamente
    print("\n🔍 Buscando GQG en dividend_fx_map:")
    for key, data in self.dividend_fx_map.items():
        if 'GQG' in key:
            print(f"\n  Key: {key}")
            dividend_data = data.get('dividend', {})
            print(f"  Symbol: {dividend_data.get('symbol', 'N/A')}")
            print(f"  Amount: {dividend_data.get('amount_original', 'N/A')}")
            print(f"  Currency: {dividend_data.get('currency_original', 'N/A')}")
            print(f"  Date: {dividend_data.get('date', 'N/A')}")
            print(f"  Tax: {dividend_data.get('tax', 'N/A')}")
            
            # Calcular net amount
            amount_orig = dividend_data.get('amount_original', Decimal('0'))
            tax = dividend_data.get('tax', Decimal('0'))
            net = amount_orig - tax
            print(f"  Net amount: {net}")
            
            # Buscar FX withdrawal coincidente
            print(f"\n  🔎 Buscando FX withdrawal coincidente:")
            for i, fx_w in enumerate(self.fx_withdrawals):
                print(f"\n    FX Withdrawal #{i+1}:")
                print(f"      Amount: {fx_w['amount']}")
                print(f"      Currency: {fx_w['currency']}")
                print(f"      Date: {fx_w['date']}")
                print(f"      Exchange rate: {fx_w.get('exchange_rate', 'N/A')}")
                
                # Verificar condiciones
                amount_match = abs(fx_w['amount'] - abs(net)) < Decimal('0.5')
                currency_match = fx_w['currency'] == dividend_data.get('currency_original', '')
                print(f"      Amount match? {amount_match} (diff: {abs(fx_w['amount'] - abs(net))})")
                print(f"      Currency match? {currency_match}")
                
                if amount_match and currency_match:
                    try:
                        div_date = datetime.strptime(dividend_data.get('date', ''), '%Y-%m-%d')
                        fx_date = datetime.strptime(fx_w['date'], '%d-%m-%Y')
                        days_diff = abs((fx_date - div_date).days)
                        date_match = days_diff <= 5
                        print(f"      Date match? {date_match} (diff: {days_diff} días)")
                        
                        if date_match:
                            print(f"      ✅ MATCH ENCONTRADO!")
                    except Exception as e:
                        print(f"      ❌ Error parsing dates: {e}")
    
    # Llamar al método original
    return original_consolidate(self)

DeGiroParser._consolidate_dividends = logged_consolidate

def test():
    csv_path = 'uploads/Degiro.csv'
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    print("\n" + "=" * 80)
    print("RESULTADO:")
    print("=" * 80)
    
    gqg_divs = [d for d in data['dividends'] if 'GQG' in d.get('symbol', '')]
    print(f"\n💰 Dividendos de GQG procesados: {len(gqg_divs)}")
    
    for div in gqg_divs[:2]:  # Solo los primeros 2
        print(f"\n  Fecha: {div.get('date')}")
        print(f"  Dividendo: {div.get('amount')} {div.get('currency')}")
        print(f"  Retención: {div.get('tax')} {div.get('currency')}")
        print(f"  Retención EUR: {div.get('tax_eur')} EUR")

if __name__ == '__main__':
    test()

