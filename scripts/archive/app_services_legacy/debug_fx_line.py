#!/usr/bin/env python3
"""Debug línea FX específica"""
import csv

with open('uploads/Degiro.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    # Buscar línea de Retirada Cambio de Divisa con HKD
    for row in reader:
        desc = row.get('Descripción', '').strip()
        if 'Retirada Cambio de Divisa' in desc and row.get('Variación', '') == 'HKD':
            print("=" * 80)
            print("LÍNEA DE RETIRADA CAMBIO DE DIVISA (HKD)")
            print("=" * 80)
            
            print("\nTODAS LAS COLUMNAS:")
            for i, (key, value) in enumerate(row.items()):
                print(f"  {i+1}. Key: '{key}' | Value: '{value}'")
            
            print("\n" + "=" * 80)
            break

