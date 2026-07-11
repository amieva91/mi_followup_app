#!/usr/bin/env python3
"""Script para debuggear el cálculo de tax_eur para GQG PARTNERS CDI"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser
import csv
from decimal import Decimal

def debug_gqg():
    csv_path = 'uploads/Degiro.csv'
    
    print("=" * 80)
    print("DEBUGGING GQG PARTNERS CDI - TAX_EUR")
    print("=" * 80)
    
    # Parsear
    parser = DeGiroParser()
    data = parser.parse(csv_path)
    
    # Buscar dividendo de GQG
    gqg_divs = [d for d in data['dividends'] if 'GQG' in d.get('symbol', '')]
    
    if gqg_divs:
        print(f"\n📊 {len(gqg_divs)} dividendo(s) de GQG encontrado(s):\n")
        for div in gqg_divs:
            print(f"  Fecha: {div.get('date')}")
            print(f"  Dividendo: {div.get('amount')} {div.get('currency')}")
            print(f"  Retención: {div.get('tax')} {div.get('currency')}")
            print(f"  Retención EUR: {div.get('tax_eur')} EUR")
            print()
    
    # Ahora buscar manualmente en el CSV las líneas relacionadas con GQG
    print("\n" + "=" * 80)
    print("BUSCANDO LÍNEAS DE GQG EN EL CSV:")
    print("=" * 80 + "\n")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        print("Columnas:", header)
        print()
        
        gqg_rows = []
        for row in reader:
            # Buscar GQG en cualquier columna
            if any('GQG' in str(cell).upper() for cell in row):
                gqg_rows.append(row)
        
        print(f"📋 {len(gqg_rows)} líneas con 'GQG' encontradas:\n")
        
        for i, row in enumerate(gqg_rows, 1):
            print(f"--- Línea {i} ---")
            for j, (col, val) in enumerate(zip(header, row)):
                if val.strip():
                    print(f"  {col}: {val}")
            # Mostrar también columnas sin nombre
            if len(row) > len(header):
                print(f"  [Columna sin nombre {len(header)}]: {row[len(header)]}")
            if len(row) > len(header) + 1:
                print(f"  [Columna sin nombre {len(header)+1}]: {row[len(header)+1]}")
            print()

if __name__ == '__main__':
    debug_gqg()

