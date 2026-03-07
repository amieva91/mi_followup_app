"""
Script de diagnóstico: Moneda BG y activos con posiciones cortas

1. Lista qué activos tienen moneda 'BG' (para identificar la moneda correcta)
2. Detecta activos con oversells (posición corta) durante el cálculo FIFO
3. Para cada activo con shorts: lista todas las transacciones con balance acumulado

Uso: cd /home/ssoo/www && source venv/bin/activate && python docs/scripts/diagnostico_moneda_bg_y_posiciones_cortas.py [user_id]
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

from app import create_app, db
from app.models import Asset, Transaction
from app.services.fifo_calculator import FIFOCalculator


# Monedas ISO 4217 comunes (BG podría ser BGN = Lev búlgaro truncado)
MONEDA_BG_INFO = """
Nota: 'BG' no es un código ISO 4217 estándar.
  - BGN = Lev búlgaro (Bulgaria)
  - Si el activo es de Bulgaria o mercados bálticos, probablemente debería ser BGN.
"""


def main(user_id: int = 1):
    app = create_app()
    with app.app_context():
        print("\n" + "=" * 80)
        print("🔍 DIAGNÓSTICO: MONEDA BG Y POSICIONES CORTAS")
        print("=" * 80)

        # 1. Activos con moneda BG
        print("\n1️⃣  ACTIVOS CON MONEDA 'BG':")
        print("-" * 80)
        assets_bg = Asset.query.filter(Asset.currency == 'BG').all()
        if not assets_bg:
            # También buscar transacciones con currency BG
            tx_bg = Transaction.query.filter(Transaction.currency == 'BG').first()
            if tx_bg:
                print("  No hay assets con currency=BG, pero SÍ hay transacciones con currency=BG.")
                print("  Transacción ejemplo:", tx_bg.id, tx_bg.transaction_type, tx_bg.asset_id)
            else:
                print("  No se encontraron assets ni transacciones con moneda 'BG'.")
        else:
            for a in assets_bg:
                print(f"  Asset ID: {a.id}")
                print(f"    • Symbol: {a.symbol}")
                print(f"    • Name: {a.name}")
                print(f"    • ISIN: {a.isin}")
                print(f"    • Type: {a.asset_type}")
                print(f"    • Currency: {a.currency}")
                print(MONEDA_BG_INFO)

        # 2. Transacciones con currency BG (puede venir de txn.currency)
        print("\n2️⃣  TRANSACCIONES CON CURRENCY 'BG':")
        print("-" * 80)
        txns_bg = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.currency == 'BG'
        ).order_by(Transaction.transaction_date).all()
        if txns_bg:
            for t in txns_bg:
                asset = t.asset
                asset_info = f"Asset {t.asset_id}: {asset.symbol if asset else 'N/A'}"
                print(f"  Txn {t.id}: {t.transaction_type} | {t.transaction_date.date()} | "
                      f"qty={t.quantity} price={t.price} | {asset_info}")
        else:
            print("  Ninguna transacción con currency='BG'.")

        # 3. Ejecutar FIFO y capturar qué activos generan posición corta
        print("\n3️⃣  ACTIVOS CON POSICIÓN CORTA (oversells detectados):")
        print("-" * 80)
        all_txns = (
            Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.asset_id.isnot(None),
                Transaction.transaction_type.in_(['BUY', 'SELL'])
            )
            .order_by(Transaction.transaction_date)
            .all()
        )
        # Agrupar por asset
        by_asset = defaultdict(list)
        for t in all_txns:
            by_asset[t.asset_id].append(t)

        assets_with_shorts = []
        for asset_id, txns in by_asset.items():
            asset = Asset.query.get(asset_id)
            sym = (asset.symbol if asset else None) or f"id:{asset_id}"
            calc = FIFOCalculator(symbol=sym)
            had_oversell = False
            max_short = 0
            for t in txns:
                if t.transaction_type == 'BUY':
                    total_cost = (t.quantity * t.price) + (t.commission or 0) + (t.fees or 0) + (t.tax or 0)
                    calc.add_buy(t.quantity, t.price, t.transaction_date, total_cost)
                elif t.transaction_type == 'SELL':
                    short_before = float(calc.short_position)
                    calc.add_sell(t.quantity, t.transaction_date)
                    if float(calc.short_position) > short_before:
                        had_oversell = True
                        max_short = max(max_short, float(calc.short_position))
            # Incluir si tuvo oversell en algún momento O si queda short al final
            if had_oversell or (calc.short_position and float(calc.short_position) > 0):
                assets_with_shorts.append({
                    'asset_id': asset_id,
                    'symbol': asset.symbol if asset else None,
                    'name': asset.name if asset else None,
                    'currency': asset.currency if asset else None,
                    'short_qty': float(calc.short_position) if calc.short_position else max_short,
                    'had_oversell': had_oversell,
                    'calc': calc,
                    'txns': txns
                })

        if not assets_with_shorts:
            print("  No se detectaron activos con posición corta.")
        else:
            for info in assets_with_shorts:
                print(f"  Asset {info['asset_id']}: {info['symbol']} ({info['name']})")
                print(f"    Moneda: {info['currency']} | Short pendiente: {info['short_qty']}")

        # 4. Listado detallado de transacciones por activo con shorts + balance acumulado
        print("\n4️⃣  DETALLE POR ACTIVO CON POSICIÓN CORTA (transacciones + balance):")
        print("-" * 80)
        for info in assets_with_shorts:
            asset_id = info['asset_id']
            symbol = info['symbol'] or 'N/A'
            name = info['name'] or 'N/A'
            print(f"\n  📌 Asset {asset_id}: {symbol} - {name}")
            print("  " + "-" * 70)
            txns = sorted(info['txns'], key=lambda t: (t.transaction_date, t.id))
            running_qty = Decimal('0')
            for t in txns:
                if t.transaction_type == 'BUY':
                    running_qty += Decimal(str(t.quantity))
                    delta = f"+{t.quantity}"
                else:
                    running_qty -= Decimal(str(t.quantity))
                    delta = f"-{t.quantity}"
                print(f"    {t.transaction_date.strftime('%Y-%m-%d %H:%M')} | "
                      f"{t.transaction_type:4} | qty {delta:>10} | "
                      f"balance acumulado: {float(running_qty):>12.2f}")
            print(f"    → Balance final: {float(running_qty):.2f} "
                  f"({'✓ OK' if running_qty >= 0 else '⚠ NEGATIVO (oversell)'})")

        print("\n" + "=" * 80)
        print("✅ DIAGNÓSTICO COMPLETADO")
        print("=" * 80 + "\n")


if __name__ == '__main__':
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(user_id)
