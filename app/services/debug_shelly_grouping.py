#!/usr/bin/env python3
"""
Script para investigar por qué SHELLY GROUP tiene 2 entradas en lugar de 1 (o 0)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser
import csv

def debug_shelly():
    csv_path = 'uploads/Degiro.csv'
    
    print("\n" + "="*80)
    print("DEBUG: AGRUPACIÓN DE SHELLY GROUP")
    print("="*80 + "\n")
    
    # Buscar todas las líneas de SHELLY en el CSV
    print("📋 LÍNEAS DE SHELLY EN EL CSV:\n")
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        shelly_rows = []
        for row in reader:
            if len(row) < 5:
                continue
            
            fecha = row[0]
            hora = row[1]
            producto = row[2] if len(row) > 2 else ''
            isin = row[3] if len(row) > 3 else ''
            descripcion = row[4] if len(row) > 4 else ''
            variacion = row[7] if len(row) > 7 else ''
            monto = row[8] if len(row) > 8 else ''
            
            if 'SHELLY' in producto.upper() and 'BG1100003166' in isin:
                shelly_rows.append({
                    'fecha': fecha,
                    'hora': hora,
                    'producto': producto,
                    'isin': isin,
                    'descripcion': descripcion,
                    'variacion': variacion,
                    'monto': monto
                })
    
    for i, row in enumerate(shelly_rows):
        print(f"{i+1}. Fecha: {row['fecha']} {row['hora']}")
        print(f"   Descripción: {row['descripcion']}")
        print(f"   Monto: {row['monto']} {row['variacion']}")
        print()
    
    # Parsear y ver qué se almacena en dividend_related_rows
    print("="*80)
    print("📊 ANÁLISIS DEL PARSER:\n")
    
    parser = DeGiroParser()
    parsed_data = parser.parse(csv_path)
    
    # Buscar en dividend_related_rows (antes de consolidación)
    print(f"Total dividend_related_rows almacenadas: {len(parser.dividend_related_rows)}")
    
    shelly_related = [r for r in parser.dividend_related_rows if 'BG1100003166' in r.get('isin', '')]
    
    print(f"\nSHELLY en dividend_related_rows: {len(shelly_related)}\n")
    
    for i, row in enumerate(shelly_related):
        print(f"{i+1}. Fecha: {row['fecha_str']} {row['fecha_hora']}")
        print(f"   Producto: {row['producto']}")
        print(f"   Descripción: {row['description']}")
        print(f"   Monto: {row['amount']} {row['currency']}")
        print()
    
    # Ver los dividendos finales
    print("="*80)
    print("📈 DIVIDENDOS FINALES:\n")
    
    shelly_divs = [d for d in parsed_data['dividends'] if 'SHELLY' in d['symbol'].upper()]
    
    print(f"Total dividendos SHELLY: {len(shelly_divs)}\n")
    
    for i, div in enumerate(shelly_divs):
        print(f"{i+1}. Fecha: {div['date']}")
        print(f"   Monto: {div['amount']:.2f} {div['currency']}")
        if div.get('amount_original'):
            print(f"   Original: {div['amount_original']:.2f} {div.get('currency_original')}")
        print()
    
    # CONCLUSIÓN
    print("="*80)
    print("🔍 CONCLUSIÓN:\n")
    
    if len(shelly_related) == 2:
        print("✅ Se encontraron 2 filas relacionadas")
        time_diff = abs((shelly_related[1]['fecha_hora'] - shelly_related[0]['fecha_hora']).total_seconds() / 3600)
        print(f"   Diferencia de tiempo: {time_diff:.2f} horas")
        
        if time_diff > 2:
            print(f"   ⚠️  PROBLEMA: Diferencia > 2 horas, NO se agruparán")
        else:
            print(f"   ✅ Diferencia <= 2 horas, deberían agruparse")
        
        # Verificar si tienen "Dividendo"
        has_dividendo_1 = shelly_related[0]['description'] == 'Dividendo'
        has_dividendo_2 = shelly_related[1]['description'] == 'Dividendo'
        
        print(f"\n   Entrada 1 tiene 'Dividendo': {has_dividendo_1}")
        print(f"   Entrada 2 tiene 'Dividendo': {has_dividendo_2}")
        
        if not (has_dividendo_1 or has_dividendo_2):
            print(f"   ⚠️  PROBLEMA: Ninguna tiene 'Dividendo', se filtrarán")
        
        # Calcular neto
        neto = sum(r['amount'] for r in shelly_related)
        print(f"\n   Neto: {neto}")
        
        if neto == 0:
            print(f"   ✅ Neto = 0, NO debería crear dividendo")

if __name__ == '__main__':
    debug_shelly()

