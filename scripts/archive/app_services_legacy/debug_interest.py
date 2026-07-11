#!/usr/bin/env python3
"""
Script para diagnosticar la sección de Interés (Apalancamiento) de IBKR
"""

import sys
import os
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

csv_files = [
    'uploads/U12722327_20230912_20240911.csv',
    'uploads/U12722327_20240912_20250911.csv',
    'uploads/U12722327_20250912_20251006.csv'
]

print("\n" + "="*80)
print("DIAGNÓSTICO: INTERÉS (APALANCAMIENTO) DE IBKR")
print("="*80 + "\n")

for csv_file in csv_files:
    if not os.path.exists(csv_file):
        continue
    
    print(f"📄 Archivo: {os.path.basename(csv_file)}")
    print("="*80 + "\n")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        in_section = False
        headers = []
        count = 0
        
        for i, row in enumerate(reader, 1):
            if not row:
                continue
            
            section_name = row[0] if len(row) > 0 else ''
            row_type = row[1] if len(row) > 1 else ''
            
            # Detectar sección (español e inglés)
            if 'Interés' == section_name or 'Interest' == section_name:
                in_section = True
                print(f"✅ Sección encontrada: {section_name} (fila {i})\n")
                
                if row_type == 'Header':
                    headers = row[2:]  # Sin las primeras 2 columnas
                    print(f"📋 HEADERS ({len(headers)} columnas):")
                    for idx, header in enumerate(headers):
                        print(f"  [{idx:2}] {header}")
                    print()
            
            # Salir de la sección
            if in_section and section_name and section_name not in ['Interés', 'Interest']:
                break
            
            # Procesar filas de datos
            if in_section and row_type == 'Data':
                count += 1
                if count <= 10:  # Mostrar los primeros 10 ejemplos
                    print(f"📊 EJEMPLO {count} (fila {i}):")
                    data_row = row[2:]
                    
                    # Mostrar raw
                    print("  Raw:")
                    for idx, val in enumerate(data_row[:6]):
                        print(f"    [{idx:2}] {val}")
                    
                    # Mapear con headers
                    if headers and len(data_row) >= len(headers):
                        row_dict = dict(zip(headers, data_row))
                        print("\n  Mapeado:")
                        print(f"    Divisa: {row_dict.get('Divisa', row_dict.get('Currency', 'N/A'))}")
                        print(f"    Fecha: {row_dict.get('Fecha', row_dict.get('Date', 'N/A'))}")
                        print(f"    Descripción: {row_dict.get('Descripción', row_dict.get('Description', 'N/A'))}")
                        print(f"    Cantidad: {row_dict.get('Cantidad', row_dict.get('Amount', 'N/A'))}")
                    print()
        
        if in_section:
            print(f"📊 Total entradas encontradas: {count}\n")
        else:
            print(f"❌ Sección NO encontrada en este archivo\n")
        
        print("="*80 + "\n")

print("✅ Diagnóstico completado")
print("="*80 + "\n")

