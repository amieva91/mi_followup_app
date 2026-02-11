#!/usr/bin/env python3
"""
Simulación de parseo CSV Revolut X - Muestra qué se extrae del CSV sin modificar BD.
Uso: python docs/scripts/simulacion_csv_revolut_x.py <ruta_al_csv>

Ejemplo: python docs/scripts/simulacion_csv_revolut_x.py uploads/revx-account-statement_2018-10-18_2026-02-08_es-es_1442ce.csv
"""
import sys
import os

# Añadir proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.parsers.revolut_x_parser import RevolutXParser


def main():
    if len(sys.argv) < 2:
        # Buscar CSV en uploads/
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        uploads = os.path.join(base, 'uploads')
        candidates = [f for f in os.listdir(uploads) if f.startswith('revx-') and f.endswith('.csv')]
        if not candidates:
            print("Uso: python simulacion_csv_revolut_x.py <ruta_al_csv>")
            print("O coloca un archivo revx-*.csv en uploads/")
            sys.exit(1)
        filepath = os.path.join(uploads, candidates[0])
        print(f"Usando: {filepath}\n")
    else:
        filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"Archivo no encontrado: {filepath}")
        sys.exit(1)

    parser = RevolutXParser()
    data = parser.parse(filepath)

    print("=" * 80)
    print("SIMULACIÓN DE PARSEO - REVOLUT X CSV")
    print("=" * 80)
    print(f"\nTotal trades extraídos: {len(data['trades'])}")
    print(f"Total holdings calculados: {len(data['holdings'])}")

    # Agrupar trades por símbolo
    by_symbol = {}
    for t in data['trades']:
        sym = t['symbol']
        if sym not in by_symbol:
            by_symbol[sym] = []
        by_symbol[sym].append(t)

    # Mostrar por símbolo (XRP, ETH, ADA)
    for symbol in ['XRP', 'ETH', 'ADA', 'BTC', 'USDT']:
        if symbol not in by_symbol:
            continue
        trades = by_symbol[symbol]
        print(f"\n{'='*60}")
        print(f"  {symbol} - {len(trades)} transacciones")
        print("=" * 60)

        qty_acum = 0
        for i, t in enumerate(trades, 1):
            fecha = t['date'].strftime('%Y-%m-%d %H:%M') if t.get('date') else '?'
            tipo = t['transaction_type']
            qty = t['quantity']
            price = t.get('price', 0)
            desc = t.get('description', '')[:50]

            if tipo == 'BUY':
                if price == 0:
                    qty_acum += qty
                    print(f"  {i:3}. {fecha}  BUY (reward)  +{qty:.6f}  →  Acum: {qty_acum:.6f}  |  {desc}")
                else:
                    qty_acum += qty
                    print(f"  {i:3}. {fecha}  BUY          +{qty:.6f} @ {price:.4f}  →  Acum: {qty_acum:.6f}")
            else:
                qty_acum -= qty
                print(f"  {i:3}. {fecha}  SELL         -{qty:.6f} @ {price:.4f}  →  Acum: {qty_acum:.6f}")

        print(f"  → Posición final {symbol}: {qty_acum:.6f}")

    # Holdings calculados por el parser
    print(f"\n{'='*80}")
    print("HOLDINGS CALCULADOS POR EL PARSER (input al importer)")
    print("=" * 80)
    for h in data['holdings']:
        print(f"  {h['symbol']}: qty={h['quantity']:.6f}, coste={h['total_cost']:.2f} €")

    # Resumen de tipos
    print(f"\n{'='*80}")
    print("RESUMEN POR TIPO")
    print("=" * 80)
    buys = [t for t in data['trades'] if t['transaction_type'] == 'BUY']
    sells = [t for t in data['trades'] if t['transaction_type'] == 'SELL']
    rewards = [t for t in data['trades'] if t.get('is_reward')]
    print(f"  BUY (compras):     {len(buys)}")
    print(f"  BUY (rewards):     {len(rewards)}")
    print(f"  SELL:              {len(sells)}")


if __name__ == '__main__':
    main()
