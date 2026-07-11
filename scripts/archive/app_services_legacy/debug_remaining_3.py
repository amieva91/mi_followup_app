#!/usr/bin/env python3
"""
Script para investigar los 3 dividendos no convertidos
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser
import csv

def analyze_non_eur_dividends():
    csv_path = 'uploads/Degiro.csv'
    
    print("\n" + "="*80)
    print("INVESTIGACIÓN: 3 DIVIDENDOS NO CONVERTIDOS")
    print("="*80 + "\n")
    
    parser = DeGiroParser()
    parsed_data = parser.parse(csv_path)
    
    # Dividendos no EUR
    non_eur = [d for d in parsed_data['dividends'] if d['currency'] != 'EUR']
    
    print(f"📊 Total no EUR: {len(non_eur)}\n")
    
    for div in non_eur:
        print("="*80)
        print(f"🔍 DIVIDENDO: {div['symbol']}")
        print(f"   Fecha: {div['date']}")
        print(f"   Monto: {div['amount']:.2f} {div['currency']}")
        print(f"   ISIN: {div.get('isin', 'N/A')}")
        print()
        
        # Buscar líneas relacionadas en el CSV
        print("   📋 LÍNEAS DEL CSV RELACIONADAS:")
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            for row in reader:
                if len(row) < 5:
                    continue
                
                fecha = row[0]
                producto = row[2] if len(row) > 2 else ''
                isin = row[3] if len(row) > 3 else ''
                descripcion = row[4] if len(row) > 4 else ''
                
                # Buscar por símbolo, ISIN o fecha cercana
                if (div['symbol'].upper() in producto.upper() or 
                    (div.get('isin') and div['isin'] in isin) or
                    (fecha and fecha.startswith(div['date'].split('-')[2]))):  # Año
                    
                    # Verificar si es relevante
                    if ('Dividendo' in descripcion or 
                        'Cambio de Divisa' in descripcion or
                        'Retención' in descripcion or
                        div['symbol'].upper() in producto.upper()):
                        
                        variacion = row[7] if len(row) > 7 else ''
                        monto = row[8] if len(row) > 8 else ''
                        
                        print(f"      {fecha} | {producto[:30]:30} | {descripcion[:40]:40} | {variacion:5} | {monto}")
        print()
        
        # Buscar conversiones FX disponibles
        print("   💱 CONVERSIONES FX DISPONIBLES EN LA MISMA MONEDA:")
        currency = div['currency']
        for fx_w in parser.fx_withdrawals:
            if fx_w['currency'] == currency:
                print(f"      Retirada: {fx_w['date']} | {fx_w['amount']:.2f} {fx_w['currency']} | Tasa: {fx_w.get('exchange_rate', 'N/A')}")
        
        if not any(fx['currency'] == currency for fx in parser.fx_withdrawals):
            print(f"      ⚠️  NO HAY CONVERSIONES FX PARA {currency}")
        print()

if __name__ == '__main__':
    analyze_non_eur_dividends()

