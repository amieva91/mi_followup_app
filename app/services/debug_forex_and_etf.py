#!/usr/bin/env python3
"""
Script para diagnosticar EUR.GBP, EUR.SGD y tipo de R2US
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.ibkr_parser import IBKRParser

csv_file = 'uploads/U12722327_20230912_20240911.csv'

print("\n" + "="*80)
print("DIAGNÓSTICO: EUR.GBP, EUR.SGD y ETF vs Stock")
print("="*80 + "\n")

parser = IBKRParser()
result = parser.parse(csv_file)

# 1. Buscar EUR.GBP y EUR.SGD en trades
print("1. BUSCANDO EUR.GBP y EUR.SGD EN TRADES")
print("="*80 + "\n")

forex_trades = []
for trade in result['trades']:
    symbol = trade.get('symbol', '')
    if 'EUR' in symbol and ('GBP' in symbol or 'SGD' in symbol):
        forex_trades.append(trade)
        print(f"Symbol: {symbol}")
        print(f"  Asset Type: {trade.get('asset_type', 'N/A')}")
        print(f"  Currency: {trade.get('currency', 'N/A')}")
        print(f"  Transaction: {trade.get('transaction_type', 'N/A')}")
        print(f"  Quantity: {trade.get('quantity', 'N/A')}")
        print(f"  Date: {trade.get('date_time', 'N/A')}")
        print()

if not forex_trades:
    print("⚠️  No se encontraron EUR.GBP ni EUR.SGD en trades\n")

# 2. Buscar en Información de Instrumento
print("="*80)
print("2. BUSCANDO EN INFORMACIÓN DE INSTRUMENTO")
print("="*80 + "\n")

if 'EUR.GBP' in parser.instrument_info:
    print("EUR.GBP encontrado:")
    print(f"  {parser.instrument_info['EUR.GBP']}\n")

if 'EUR.SGD' in parser.instrument_info:
    print("EUR.SGD encontrado:")
    print(f"  {parser.instrument_info['EUR.SGD']}\n")

# 3. Buscar en la sección "Operaciones" raw
print("="*80)
print("3. BUSCANDO EN SECCIÓN 'OPERACIONES' (raw)")
print("="*80 + "\n")

section = parser.sections.get('Operaciones') or parser.sections.get('Trades')
if section:
    for row in section['data']:
        if len(row) > 2:
            symbol = row[1] if len(row) > 1 else ''  # Símbolo suele estar en posición 1
            if 'EUR' in str(symbol) and ('GBP' in str(symbol) or 'SGD' in str(symbol)):
                print(f"Fila encontrada con {symbol}:")
                for idx, val in enumerate(row[:10]):
                    print(f"  [{idx}] {val}")
                print()

# 4. Verificar R2US (ETF)
print("="*80)
print("4. VERIFICANDO R2US (SPDR RUSSELL 2000)")
print("="*80 + "\n")

if 'R2US' in parser.instrument_info:
    print("R2US en instrument_info:")
    info = parser.instrument_info['R2US']
    print(f"  ISIN: {info.get('isin', 'N/A')}")
    print(f"  Name: {info.get('name', 'N/A')}")
    print(f"  Exchange: {info.get('exchange', 'N/A')}")
    print(f"  Asset Type: {info.get('asset_type', 'N/A')}")
    print()

# Buscar en trades
for trade in result['trades']:
    if trade.get('symbol') == 'R2US':
        print(f"R2US en trade:")
        print(f"  Asset Type: {trade.get('asset_type', 'N/A')}")
        print(f"  Transaction: {trade.get('transaction_type', 'N/A')}")
        print(f"  Date: {trade.get('date_time', 'N/A')}")
        break

# 5. Buscar R2US en raw de "Información de instrumento financiero"
print("\n" + "="*80)
print("5. R2US EN 'INFORMACIÓN DE INSTRUMENTO FINANCIERO' (raw)")
print("="*80 + "\n")

section = parser.sections.get('Información de instrumento financiero') or \
          parser.sections.get('Financial Instrument Information')
if section:
    for row in section['data']:
        if len(row) > 1 and row[1] == 'R2US':  # Símbolo en posición 1
            print("Fila R2US encontrada:")
            for idx, val in enumerate(row):
                print(f"  [{idx}] {val}")
            print()
            
            # Mapear con headers
            if section['headers']:
                row_dict = dict(zip(section['headers'], row))
                print("Mapeado con headers:")
                print(f"  Símbolo: {row_dict.get('Símbolo', 'N/A')}")
                print(f"  Descripción: {row_dict.get('Descripción', 'N/A')}")
                print(f"  Tipo: {row_dict.get('Tipo', 'N/A')}")
                print(f"  Asset Type detectado: {'ETF' if 'ETF' in row_dict.get('Tipo', '').upper() else 'Stock'}")
            break

print("\n" + "="*80)

