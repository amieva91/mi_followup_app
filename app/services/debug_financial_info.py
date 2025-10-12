#!/usr/bin/env python3
"""
Script para ver específicamente la sección de Información de instrumento financiero
"""

import sys
import os
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

csv_file = 'uploads/U12722327_20230912_20240911.csv'

print("\n" + "="*80)
print("INFORMACIÓN DE INSTRUMENTO FINANCIERO")
print("="*80 + "\n")

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    
    in_section = False
    count = 0
    
    for i, row in enumerate(reader, 1):
        if not row:
            continue
        
        section_name = row[0] if len(row) > 0 else ''
        row_type = row[1] if len(row) > 1 else ''
        
        # Detectar inicio de sección
        if 'Información de instrumento financiero' in section_name or 'Financial Instrument Information' in section_name:
            in_section = True
        
        # Salir de la sección cuando empiece otra
        if in_section and section_name and section_name != 'Información de instrumento financiero' and section_name != 'Financial Instrument Information':
            break
        
        # Imprimir filas de la sección
        if in_section:
            if row_type == 'Header':
                print(f"\n📋 HEADERS (fila {i}):")
                print(f"Total columnas: {len(row)}\n")
                for idx, header in enumerate(row):
                    print(f"  [{idx:2}] {header}")
                print()
            elif row_type == 'Data':
                count += 1
                if count <= 5:  # Mostrar solo los primeros 5 ejemplos
                    print(f"\n📊 DATA {count} (fila {i}):")
                    print(f"Total columnas: {len(row)}\n")
                    for idx, value in enumerate(row):
                        print(f"  [{idx:2}] {value}")
                    print()

print(f"\n✅ Total instrumentos en la sección: {count}")
print("="*80)

