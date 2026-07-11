#!/usr/bin/env python3
"""Analizar transacciones de VARTA AG"""
import csv
from datetime import datetime

varta_transactions = []

with open('uploads/TransaccionesDegiro.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    for row in reader:
        producto = row.get('Producto', '').strip()
        if 'VARTA' in producto.upper():
            numero_str = row.get('Número', '0').replace(',', '.')
            try:
                quantity = float(numero_str)
            except:
                continue
            
            if quantity == 0:
                continue
            
            fecha_str = row.get('Fecha', '')
            hora_str = row.get('Hora', '')
            
            # Parsear fecha
            try:
                dt = datetime.strptime(f"{fecha_str} {hora_str}", '%d-%m-%Y %H:%M')
            except:
                try:
                    dt = datetime.strptime(fecha_str, '%d-%m-%Y')
                except:
                    dt = None
            
            varta_transactions.append({
                'date': dt,
                'date_str': fecha_str,
                'time_str': hora_str,
                'quantity': quantity,
                'type': 'BUY' if quantity > 0 else 'SELL'
            })

# Ordenar por fecha
varta_transactions.sort(key=lambda x: x['date'] if x['date'] else datetime.min)

print("=" * 100)
print("ANÁLISIS DE TRANSACCIONES DE VARTA AG")
print("=" * 100)

balance = 0
print(f"\n{'Fecha':<20} {'Hora':<10} {'Tipo':<6} {'Cantidad':>10} {'Balance':>10}")
print("-" * 100)

for t in varta_transactions:
    date_display = t['date'].strftime('%Y-%m-%d') if t['date'] else t['date_str']
    balance += t['quantity']
    
    print(f"{date_display:<20} {t['time_str']:<10} {t['type']:<6} {t['quantity']:>10.0f} {balance:>10.0f}")

print("-" * 100)
print(f"\n📊 RESUMEN:")
print(f"   Total transacciones: {len(varta_transactions)}")
print(f"   Balance final: {balance:.0f}")
print(f"   Compras totales: {sum(t['quantity'] for t in varta_transactions if t['quantity'] > 0):.0f}")
print(f"   Ventas totales: {abs(sum(t['quantity'] for t in varta_transactions if t['quantity'] < 0)):.0f}")

if balance != 0:
    print(f"\n⚠️  ADVERTENCIA: Balance no es 0, la posición está {'LARGA' if balance > 0 else 'CORTA'}")
else:
    print(f"\n✅ Balance es 0, todas las posiciones están cerradas")

print("\n" + "=" * 100)

