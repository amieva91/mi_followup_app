#!/usr/bin/env python3
"""Inspeccionar estructura del CSV DeGiro Estado de Cuenta"""
import csv

with open('uploads/Degiro.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    # Leer primera fila
    row = next(reader)
    
    print("=" * 80)
    print("ESTRUCTURA DEL CSV DEGIRO - ESTADO DE CUENTA")
    print("=" * 80)
    
    print(f"\nCOLUMNAS ({len(row.keys())} total):")
    for i, col in enumerate(row.keys(), 1):
        valor = row[col]
        print(f"  {i:2}. '{col}' = '{valor}'")
    
    # Buscar una línea de dividendo
    print(f"\n" + "=" * 80)
    print("BUSCANDO LÍNEA DE DIVIDENDO...")
    print("=" * 80)
    
    f.seek(0)  # Volver al inicio
    reader = csv.DictReader(f)
    
    for row in reader:
        if row.get('Descripción', '').strip() == 'Dividendo':
            print(f"\nENCONTRADO - Producto: {row.get('Producto', '')}")
            print(f"\nCOLUMNAS DE ESTA FILA:")
            for i, (col, val) in enumerate(row.items(), 1):
                if val:  # Solo mostrar columnas con valor
                    print(f"  {i:2}. '{col}' = '{val}'")
            break
    
    print("\n" + "=" * 80)

