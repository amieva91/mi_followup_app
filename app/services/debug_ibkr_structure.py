#!/usr/bin/env python3
"""
Script para ver la estructura exacta del CSV de IBKR
"""

import sys
import os
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

csv_file = 'uploads/U12722327_20230912_20240911.csv'

print("\n" + "="*80)
print("ESTRUCTURA DEL CSV DE IBKR")
print("="*80 + "\n")

in_financial_info = False
in_dividends = False

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    
    for i, row in enumerate(reader, 1):
        if not row:
            continue
        
        section_name = row[0] if len(row) > 0 else ''
        row_type = row[1] if len(row) > 1 else ''
        
        # Detectar inicio de sección de instrumentos
        if 'Información de instrumento financiero' in section_name or 'Financial Instrument Information' in section_name:
            in_financial_info = True
            print("="*80)
            print(f"SECCIÓN: {section_name}")
            print("="*80 + "\n")
        
        # Detectar inicio de sección de dividendos
        if 'Dividendos' in section_name or 'Dividends' in section_name:
            in_dividends = True
            in_financial_info = False
            print("\n" + "="*80)
            print(f"SECCIÓN: {section_name}")
            print("="*80 + "\n")
        
        # Imprimir filas de información de instrumentos
        if in_financial_info:
            if row_type == 'Header':
                print(f"HEADERS (fila {i}):")
                for idx, header in enumerate(row):
                    print(f"  [{idx}] {header}")
                print()
            elif row_type == 'Data':
                print(f"DATA (fila {i}):")
                for idx, value in enumerate(row):
                    print(f"  [{idx}] {value}")
                print()
                # Limitar a 3 ejemplos
                if i > 100:
                    in_financial_info = False
        
        # Imprimir filas de dividendos
        if in_dividends:
            if row_type == 'Header':
                print(f"HEADERS (fila {i}):")
                for idx, header in enumerate(row):
                    print(f"  [{idx}] {header}")
                print()
            elif row_type == 'Data':
                print(f"DATA (fila {i}):")
                for idx, value in enumerate(row[:10]):  # Solo primeros 10 campos
                    print(f"  [{idx}] {value}")
                print()
                # Limitar a 10 filas
                if i > 350:
                    break

print("\n" + "="*80)

