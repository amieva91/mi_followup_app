#!/usr/bin/env python3
"""
Script para diagnosticar el parsing de IBKR
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.ibkr_parser import IBKRParser

# Parsear el CSV
parser = IBKRParser()

# Usar uno de tus archivos IBKR
csv_files = [
    'uploads/U12722327_20230912_20240911.csv',
    'uploads/U12722327_20240912_20250911.csv',
    'uploads/U12722327_20250912_20251006.csv'
]

print("\n" + "="*80)
print("DIAGNÓSTICO: PARSING DE IBKR")
print("="*80 + "\n")

# Probar con el primer archivo que exista
for csv_file in csv_files:
    if os.path.exists(csv_file):
        print(f"📄 Parseando: {csv_file}\n")
        
        result = parser.parse(csv_file)
        
        # 1. Verificar Información de Instrumento
        print("="*80)
        print("1. INFORMACIÓN DE INSTRUMENTO FINANCIERO")
        print("="*80 + "\n")
        
        if parser.instrument_info:
            print(f"Total instrumentos: {len(parser.instrument_info)}\n")
            for symbol, info in list(parser.instrument_info.items())[:10]:
                print(f"Symbol: {symbol}")
                print(f"  ISIN: {info.get('isin', 'N/A')}")
                print(f"  Name: {info.get('name', 'N/A')}")
                print(f"  Exchange: {info.get('exchange', 'N/A')}")
                print(f"  Type: {info.get('asset_type', 'N/A')}")
                print()
        else:
            print("⚠️  NO SE ENCONTRÓ INFORMACIÓN DE INSTRUMENTOS\n")
        
        # 2. Verificar Trades
        print("="*80)
        print("2. TRADES (primeras 5)")
        print("="*80 + "\n")
        
        for i, trade in enumerate(result['trades'][:5], 1):
            print(f"{i}. {trade.get('symbol')}")
            print(f"   Name: {trade.get('name', 'N/A')}")
            print(f"   Exchange: {trade.get('exchange', 'N/A')}")
            print(f"   Type: {trade.get('asset_type', 'N/A')}")
            print(f"   ISIN: {trade.get('isin', 'N/A')}")
            print()
        
        # 3. Verificar Dividendos
        print("="*80)
        print("3. DIVIDENDOS")
        print("="*80 + "\n")
        
        dividends = result.get('dividends', [])
        print(f"Total dividendos detectados: {len(dividends)}\n")
        
        if dividends:
            for i, div in enumerate(dividends[:10], 1):
                print(f"{i}. {div.get('symbol')} - {div.get('date')}")
                print(f"   Name: {div.get('name', 'N/A')}")
                print(f"   Amount: {div.get('amount', 0):.2f} EUR")
                print(f"   Amount Original: {div.get('amount_original', 0):.2f} {div.get('currency_original', 'N/A')}")
                print(f"   ISIN: {div.get('isin', 'N/A')}")
                print()
        else:
            print("⚠️  NO SE DETECTARON DIVIDENDOS\n")
            print("Verificando sección 'Dividendos' en el CSV...\n")
            
            # Revisar qué hay en la sección de dividendos
            div_section = parser.sections.get('Dividendos') or parser.sections.get('Dividends')
            if div_section:
                print(f"✓ Sección encontrada")
                print(f"  Headers: {div_section.get('headers', [])}")
                print(f"  Total filas: {len(div_section.get('data', []))}")
                print(f"\n  Primeras 10 filas:")
                for i, row in enumerate(div_section.get('data', [])[:10], 1):
                    print(f"    {i}. {row}")
                print()
            else:
                print("❌ Sección 'Dividendos' NO encontrada en el CSV\n")
                print("Secciones disponibles:")
                for section_name in parser.sections.keys():
                    print(f"  - {section_name}")
        
        break  # Solo procesar el primer archivo
else:
    print("❌ No se encontraron archivos CSV de IBKR en uploads/")

print("\n" + "="*80)

