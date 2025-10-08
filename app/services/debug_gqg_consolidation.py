#!/usr/bin/env python3
"""Script para debuggear la consolidación de dividendos de GQG"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import csv
from decimal import Decimal
from datetime import datetime, timedelta

def debug_consolidation():
    csv_path = 'uploads/Degiro.csv'
    
    print("=" * 80)
    print("DEBUGGING CONSOLIDACIÓN GQG")
    print("=" * 80)
    
    # Leer CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        # Buscar las 4 líneas de GQG del 29-30/09/2025
        gqg_sept = []
        for row in reader:
            date = row[0]
            if ('29-09-2025' in date or '30-09-2025' in date) and any('GQG' in str(cell).upper() for cell in row):
                gqg_sept.append(row)
        
        print(f"\n📋 {len(gqg_sept)} líneas de GQG en 29-30/09/2025:\n")
        
        for i, row in enumerate(gqg_sept, 1):
            print(f"--- Línea {i} ---")
            print(f"  Fecha: {row[0]}")
            print(f"  Producto: {row[3]}")
            print(f"  Descripción: {row[5]}")
            print(f"  Tipo: {row[6]}")
            print(f"  Variación: {row[7]}")
            print(f"  Monto (col 8): {row[8] if len(row) > 8 else 'N/A'}")
            print(f"  Saldo (col 9): {row[9] if len(row) > 9 else 'N/A'}")
            print(f"  Balance (col 10): {row[10] if len(row) > 10 else 'N/A'}")
            print()
    
    print("=" * 80)
    print("SIMULANDO CONSOLIDACIÓN:")
    print("=" * 80)
    
    # Datos extraídos manualmente
    dividendo_bruto = Decimal('152.74')
    retencion = Decimal('22.91')
    divisa_dividendo = 'AUD'
    fecha_dividendo = '2025-09-29'
    
    # FX Withdrawal
    fx_withdrawal_amount = Decimal('129.83')
    fx_withdrawal_currency = 'AUD'
    fx_withdrawal_rate = Decimal('17.873')
    fx_withdrawal_date = '2025-09-30'
    
    # FX Deposit
    fx_deposit_amount = Decimal('72.64')
    fx_deposit_currency = 'EUR'
    fx_deposit_date = '2025-09-30'
    
    print(f"\n📊 Dividendo bruto: {dividendo_bruto} {divisa_dividendo}")
    print(f"📊 Retención: {retencion} {divisa_dividendo}")
    print(f"📊 Monto neto: {dividendo_bruto - retencion} {divisa_dividendo}")
    print()
    print(f"💱 FX Withdrawal: {fx_withdrawal_amount} {fx_withdrawal_currency} (rate: {fx_withdrawal_rate})")
    print(f"💱 FX Deposit: {fx_deposit_amount} {fx_deposit_currency}")
    print()
    
    # Verificar matching
    net_amount = dividendo_bruto - retencion
    print(f"✅ Net amount match: {net_amount} = {fx_withdrawal_amount}? {abs(net_amount - fx_withdrawal_amount) < Decimal('0.5')}")
    
    # Verificar fecha (dentro de 5 días)
    date_div = datetime.strptime(fecha_dividendo, '%Y-%m-%d')
    date_fx = datetime.strptime(fx_withdrawal_date, '%Y-%m-%d')
    days_diff = abs((date_fx - date_div).days)
    print(f"✅ Date match: {days_diff} días de diferencia (< 5)? {days_diff <= 5}")
    
    # Calcular tax_eur
    tax_eur = retencion / fx_withdrawal_rate
    print(f"\n💰 Retención en EUR: {retencion} / {fx_withdrawal_rate} = {tax_eur:.2f} EUR")
    
    # Verificar relación numérica
    calc_eur = fx_withdrawal_amount / fx_withdrawal_rate
    print(f"✅ Verificación: {fx_withdrawal_amount} / {fx_withdrawal_rate} = {calc_eur:.2f} EUR (esperado: {fx_deposit_amount})")

if __name__ == '__main__':
    debug_consolidation()

