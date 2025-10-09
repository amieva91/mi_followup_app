#!/usr/bin/env python3
"""Script para verificar la nueva lógica unificada de dividendos"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

def test():
    csv_path = 'uploads/Degiro.csv'
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    print("=" * 80)
    print("VERIFICACIÓN DE LÓGICA UNIFICADA DE DIVIDENDOS")
    print("=" * 80)
    
    # Casos de prueba
    test_cases = [
        ('GQG PARTNERS CDI', '2025-09-29', 72.64, 152.74, 'AUD'),
        ('CONSUN PHARMACEUTICAL', '2025-09-22', 323.22, 2970.0, 'HKD'),
        ('PAX GLOBAL', '2025-09-26', 164.29, 1500.0, 'HKD'),
        ('GRIFOLS SA', '2025-08-15', 41.55, None, 'EUR'),
        ('ALIBABA', '2025-07-11', None, None, 'USD'),  # Caso complejo
    ]
    
    for symbol_search, fecha_esperada, eur_esperado, original_esperado, currency_esperado in test_cases:
        divs = [d for d in data['dividends'] if symbol_search in d.get('symbol', '')]
        divs_fecha = [d for d in divs if fecha_esperada in d.get('date', '')]
        
        print(f"\n{'=' * 80}")
        print(f"🔍 {symbol_search} ({fecha_esperada})")
        print(f"{'=' * 80}")
        
        if divs_fecha:
            div = divs_fecha[0]
            print(f"✅ ENCONTRADO:")
            print(f"   Dividendo: {div.get('amount')} {div.get('currency')}")
            if 'amount_original' in div and div.get('amount_original'):
                print(f"   Original: {div.get('amount_original')} {div.get('currency_original')}")
            print(f"   Retención: {div.get('tax')}")
            if div.get('tax_eur'):
                print(f"   Retención EUR: {div.get('tax_eur')}")
            
            # Verificar si coincide con lo esperado
            if eur_esperado:
                if abs(div.get('amount', 0) - eur_esperado) < 0.5:
                    print(f"   ✅ EUR correcto: {div.get('amount')} ≈ {eur_esperado}")
                else:
                    print(f"   ❌ EUR incorrecto: {div.get('amount')} ≠ {eur_esperado}")
            
            if original_esperado:
                if div.get('amount_original'):
                    if abs(div.get('amount_original', 0) - original_esperado) < 0.5:
                        print(f"   ✅ Original correcto: {div.get('amount_original')} ≈ {original_esperado}")
                    else:
                        print(f"   ❌ Original incorrecto: {div.get('amount_original')} ≠ {original_esperado}")
        else:
            print(f"❌ NO ENCONTRADO")
            if divs:
                print(f"   (Pero hay {len(divs)} dividendos de {symbol_search} en otras fechas)")
    
    print(f"\n{'=' * 80}")
    print(f"📊 RESUMEN:")
    print(f"{'=' * 80}")
    print(f"Total dividendos: {len(data['dividends'])}")
    
    # Mostrar algunos casos complejos
    print(f"\n🔍 CASOS COMPLEJOS:")
    alibaba = [d for d in data['dividends'] if 'ALIBABA' in d.get('symbol', '')]
    if alibaba:
        print(f"   ALIBABA: {len(alibaba)} dividendos")
        for d in alibaba[:2]:  # Solo los primeros 2
            print(f"      {d.get('date')}: {d.get('amount')} {d.get('currency')}")
            if d.get('amount_original'):
                print(f"         Original: {d.get('amount_original')} {d.get('currency_original')}")

if __name__ == '__main__':
    test()

