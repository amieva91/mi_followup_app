#!/usr/bin/env python3
"""
Script para probar el procesamiento de dividendos con formato Accenture
(dos "Retirada Cambio de Divisa" en lugar de Retirada + Ingreso)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test_accenture():
    csv_path = 'uploads/Degiro.csv'
    
    print("\n" + "="*80)
    print("TEST: DIVIDENDOS FORMATO ACCENTURE")
    print("="*80 + "\n")
    
    parser = DeGiroParser()
    parsed_data = parser.parse(csv_path)
    
    # Buscar dividendos de Accenture
    accenture_divs = [d for d in parsed_data['dividends'] if 'ACCENTURE' in d['symbol'].upper()]
    
    print(f"📊 Total dividendos detectados: {len(parsed_data['dividends'])}")
    print(f"🔍 Dividendos de ACCENTURE encontrados: {len(accenture_divs)}\n")
    
    if accenture_divs:
        for div in accenture_divs:
            print(f"  ✅ {div['date']}")
            print(f"     Símbolo: {div['symbol']}")
            print(f"     Monto: {div['amount']:.2f} {div['currency']}")
            if div.get('amount_original') and div.get('currency_original'):
                print(f"     Original: {div['amount_original']:.2f} {div['currency_original']}")
            print(f"     ISIN: {div['isin']}")
            print()
    else:
        print("  ⚠️  No se encontraron dividendos de Accenture")
    
    # Verificar que NO estén en EUR original (deberían estar convertidos)
    accenture_not_converted = [d for d in accenture_divs if d['currency'] != 'EUR']
    if accenture_not_converted:
        print("\n⚠️  ADVERTENCIA: Hay dividendos de Accenture que NO se convirtieron a EUR:")
        for div in accenture_not_converted:
            print(f"  - {div['date']}: {div['amount']:.2f} {div['currency']}")
    else:
        print("\n✅ Todos los dividendos de Accenture están en EUR")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    test_accenture()

