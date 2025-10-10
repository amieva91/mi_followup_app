#!/usr/bin/env python3
"""
Script para probar la lógica unificada de conversión FX
Verifica que no se rompan los casos anteriores y que funcionen los nuevos
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test_all_cases():
    csv_path = 'uploads/Degiro.csv'
    
    print("\n" + "="*80)
    print("TEST: LÓGICA UNIFICADA DE CONVERSIÓN FX")
    print("="*80 + "\n")
    
    parser = DeGiroParser()
    parsed_data = parser.parse(csv_path)
    
    dividends = parsed_data['dividends']
    
    print(f"📊 Total dividendos detectados: {len(dividends)}")
    print()
    
    # Casos de prueba específicos
    test_cases = {
        'GQG PARTNERS': {
            'date': '2024-09-27',
            'currency_original': 'AUD',
            'expected_eur': True,
            'description': 'Caso agrupado (nuevo)'
        },
        'SRG GLOBAL': {
            'date': '2024-09-27',
            'currency_original': 'AUD',
            'expected_eur': True,
            'description': 'Caso agrupado (nuevo)'
        },
        'CONSUN PHARMACEUTICAL': {
            'date': '2025-01-09',
            'currency_original': 'HKD',
            'expected_eur': True,
            'description': 'Caso individual (anterior)'
        },
        'PAX GLOBAL': {
            'date': '2025-09-26',
            'currency_original': 'HKD',
            'expected_eur': True,
            'description': 'Caso individual sin retención (anterior)'
        },
        'GRIFOLS': {
            'date': '2025-01-14',
            'currency_original': None,  # EUR directo
            'expected_eur': True,
            'description': 'Caso EUR directo (anterior)'
        },
        'ALIBABA': {
            'date': '2024-11-26',
            'currency_original': 'USD',
            'expected_eur': True,
            'description': 'Caso complejo (anterior)'
        },
        'ACCENTURE': {
            'date': '2021-08-16',
            'currency_original': 'USD',
            'expected_eur': True,
            'description': 'Caso FX alternativo (anterior)'
        }
    }
    
    print("🧪 VERIFICACIÓN DE CASOS ESPECÍFICOS:\n")
    
    for asset_name, criteria in test_cases.items():
        matching_divs = [
            d for d in dividends 
            if asset_name.upper() in d['symbol'].upper() and 
            (criteria['date'] in d['date'] if criteria.get('date') else True)
        ]
        
        if matching_divs:
            div = matching_divs[0]
            is_eur = div['currency'] == 'EUR'
            has_original = div.get('currency_original') is not None
            
            status = "✅" if is_eur == criteria['expected_eur'] else "❌"
            print(f"{status} {asset_name}")
            print(f"   Descripción: {criteria['description']}")
            print(f"   Fecha: {div['date']}")
            print(f"   Monto: {div['amount']:.2f} {div['currency']}")
            if has_original:
                print(f"   Original: {div['amount_original']:.2f} {div['currency_original']}")
            print()
        else:
            print(f"⚠️  {asset_name} - NO ENCONTRADO")
            print(f"   Descripción: {criteria['description']}")
            print()
    
    # Verificar dividendos no EUR (deberían ser 0 idealmente)
    non_eur_dividends = [d for d in dividends if d['currency'] != 'EUR']
    print(f"\n📈 RESUMEN:")
    print(f"   Total dividendos: {len(dividends)}")
    print(f"   En EUR: {len(dividends) - len(non_eur_dividends)}")
    print(f"   No EUR (a revisar): {len(non_eur_dividends)}")
    
    if non_eur_dividends:
        print(f"\n⚠️  DIVIDENDOS NO CONVERTIDOS:")
        for div in non_eur_dividends[:10]:  # Mostrar primeros 10
            print(f"   - {div['date']}: {div['symbol'][:30]} = {div['amount']:.2f} {div['currency']}")
    else:
        print(f"\n✅ TODOS los dividendos están en EUR")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    test_all_cases()

