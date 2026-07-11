#!/usr/bin/env python3
"""
Script para buscar EUR.GBP en el CSV de IBKR
"""

import sys
import os
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

csv_file = 'uploads/U12722327_20230912_20240911.csv'

print("\n" + "="*80)
print("BUSCANDO EUR.GBP EN EL CSV")
print("="*80 + "\n")

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    
    in_trades = False
    trades_headers = []
    
    for i, row in enumerate(reader, 1):
        if not row:
            continue
        
        section_name = row[0] if len(row) > 0 else ''
        row_type = row[1] if len(row) > 1 else ''
        
        # Detectar sección Operaciones/Trades
        if 'Operaciones' in section_name or 'Trades' in section_name:
            in_trades = True
            if row_type == 'Header':
                trades_headers = row[2:]  # Headers sin las primeras 2 columnas
                print(f"📋 HEADERS DE OPERACIONES (fila {i}):")
                for idx, header in enumerate(trades_headers):
                    print(f"  [{idx:2}] {header}")
                print()
        
        # Salir de la sección cuando empiece otra
        if in_trades and section_name and section_name != 'Operaciones' and section_name != 'Trades':
            break
        
        # Buscar EUR.GBP en las filas
        if 'EUR.GBP' in str(row):
            print(f"✅ ENCONTRADO EN FILA {i}")
            print(f"Tipo: {row_type}")
            print(f"Total columnas: {len(row)}\n")
            
            if in_trades and row_type == 'Data':
                print("📊 DATOS RAW (primeras 20 columnas):")
                for idx, val in enumerate(row[:20]):
                    print(f"  [{idx:2}] {val}")
                print()
                
                # Mapear con headers
                if trades_headers:
                    data_row = row[2:]  # Datos sin las primeras 2 columnas
                    row_dict = dict(zip(trades_headers, data_row))
                    
                    print("🗺️  MAPEADO CON HEADERS:")
                    print(f"  Categoría de activo: {row_dict.get('Categoría de activo', 'N/A')}")
                    print(f"  Símbolo: {row_dict.get('Símbolo', 'N/A')}")
                    print(f"  Fecha/Hora: {row_dict.get('Fecha/Hora', 'N/A')}")
                    print(f"  Cantidad: {row_dict.get('Cantidad', 'N/A')}")
                    print(f"  Precio trans.: {row_dict.get('Precio trans.', 'N/A')}")
                    print(f"  Divisa: {row_dict.get('Divisa', 'N/A')}")
                    print(f"  Productos: {row_dict.get('Productos', 'N/A')}")
                    print(f"  DataDiscriminator: {row_dict.get('DataDiscriminator', 'N/A')}")
                print()
            else:
                print("📊 DATOS RAW (todas las columnas):")
                for idx, val in enumerate(row):
                    print(f"  [{idx:2}] {val}")
                print()
            
            print("-" * 80 + "\n")

print("="*80)

