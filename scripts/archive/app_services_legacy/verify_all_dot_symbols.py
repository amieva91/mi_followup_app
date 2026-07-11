#!/usr/bin/env python3
"""
Script para verificar TODOS los símbolos con punto en el CSV
"""

import sys
import os
import csv
from collections import defaultdict
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

csv_files = [
    'uploads/U12722327_20230912_20240911.csv',
    'uploads/U12722327_20240912_20250911.csv',
    'uploads/U12722327_20250912_20251006.csv'
]

print("\n" + "="*80)
print("VERIFICACIÓN: TODOS LOS SÍMBOLOS CON PUNTO EN LOS CSVs")
print("="*80 + "\n")

dot_symbols = defaultdict(lambda: {'count': 0, 'asset_type': set(), 'files': set()})

for csv_file in csv_files:
    if not os.path.exists(csv_file):
        continue
    
    print(f"📄 Procesando: {csv_file}")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        in_trades = False
        trades_headers = []
        
        for row in reader:
            if not row:
                continue
            
            section_name = row[0] if len(row) > 0 else ''
            row_type = row[1] if len(row) > 1 else ''
            
            # Detectar sección Operaciones/Trades
            if 'Operaciones' in section_name or 'Trades' in section_name:
                in_trades = True
                if row_type == 'Header':
                    trades_headers = row[2:]
            
            # Salir de la sección
            if in_trades and section_name and section_name not in ['Operaciones', 'Trades']:
                break
            
            # Procesar filas de datos
            if in_trades and row_type == 'Data' and trades_headers:
                data_row = row[2:]
                if len(data_row) >= len(trades_headers):
                    row_dict = dict(zip(trades_headers, data_row))
                    
                    symbol = row_dict.get('Símbolo', row_dict.get('Symbol', ''))
                    asset_type = row_dict.get('Categoría de activo', row_dict.get('Asset Category', ''))
                    discriminator = row_dict.get('DataDiscriminator', '')
                    
                    if '.' in symbol and discriminator == 'Order':
                        dot_symbols[symbol]['count'] += 1
                        dot_symbols[symbol]['asset_type'].add(asset_type)
                        dot_symbols[symbol]['files'].add(os.path.basename(csv_file))

print("\n" + "="*80)
print("RESULTADOS")
print("="*80 + "\n")

if dot_symbols:
    print(f"📋 Total símbolos con punto encontrados: {len(dot_symbols)}\n")
    
    forex = []
    non_forex = []
    
    for symbol, data in sorted(dot_symbols.items()):
        asset_types = ', '.join(data['asset_type'])
        
        # Verificar si es Forex
        is_forex = any('fórex' in at.lower() or 'forex' in at.lower() for at in data['asset_type'])
        
        if is_forex:
            forex.append((symbol, asset_types, data['count']))
        else:
            non_forex.append((symbol, asset_types, data['count']))
    
    print(f"✅ FOREX (con 'Fórex' en Categoría de activo): {len(forex)}")
    for symbol, types, count in forex[:10]:  # Mostrar solo los primeros 10
        print(f"   - {symbol:20} | {types:30} | {count:3} operaciones")
    if len(forex) > 10:
        print(f"   ... y {len(forex) - 10} más")
    
    print(f"\n⚠️  NO FOREX (NO tienen 'Fórex' pero tienen punto): {len(non_forex)}")
    for symbol, types, count in non_forex:
        print(f"   - {symbol:20} | {types:30} | {count:3} operaciones")
    
    if non_forex:
        print("\n" + "="*80)
        print("❌ PROBLEMA DETECTADO")
        print("="*80)
        print("\nHay activos con punto que NO son Forex.")
        print("El filtro 'if \".\" in symbol' eliminará también estos activos.")
        print("\nSOLUCIÓN:")
        print("  Usar el filtro por asset_type: if 'fórex' in asset_type.lower()")
    else:
        print("\n" + "="*80)
        print("✅ SEGURO USAR FILTRO POR PUNTO")
        print("="*80)
        print("\nTODOS los símbolos con punto son Forex.")
        print("Es seguro usar: if '.' in symbol: continue")
else:
    print("✅ No se encontraron símbolos con punto\n")

print("\n" + "="*80)

