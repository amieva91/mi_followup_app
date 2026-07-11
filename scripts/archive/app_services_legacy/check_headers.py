#!/usr/bin/env python3
"""
Script para verificar headers exactos
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.ibkr_parser import IBKRParser

parser = IBKRParser()
csv_file = 'uploads/U12722327_20230912_20240911.csv'
parser._read_sections(csv_file)

# Ver headers de instrumento financiero
section = parser.sections.get('Información de instrumento financiero') or \
          parser.sections.get('Financial Instrument Information')

if section:
    print("\n📋 HEADERS EXACTOS:")
    print("="*80)
    for idx, header in enumerate(section['headers']):
        print(f"[{idx}] '{header}'")
    print("="*80)
    
    # Simular parsing
    print("\n🔍 PROBANDO DICT MAPPING:")
    print("="*80)
    if section['data']:
        row = section['data'][0]
        instrument_dict = dict(zip(section['headers'], row))
        
        print(f"Símbolo: '{instrument_dict.get('Símbolo', 'N/A')}'")
        print(f"Descripción: '{instrument_dict.get('Descripción', 'N/A')}'")
        print(f"Id. de seguridad: '{instrument_dict.get('Id. de seguridad', 'N/A')}'")
        
        # Probar variaciones de exchange
        print(f"\nProbando Exchange:")
        print(f"  'Merc. de cotiz.': '{instrument_dict.get('Merc. de cotiz.', 'N/A')}'")
        print(f"  'Merc. de cotización': '{instrument_dict.get('Merc. de cotización', 'N/A')}'")
        print(f"  'Listing Exch': '{instrument_dict.get('Listing Exch', 'N/A')}'")
        
        # Mostrar todos los keys
        print(f"\nTodos los keys disponibles:")
        for key in instrument_dict.keys():
            print(f"  - '{key}'")
    print("="*80)

