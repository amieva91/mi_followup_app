#!/usr/bin/env python3
"""Verificar si las transacciones tienen comisiones registradas"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Transaction

app = create_app()
app.app_context().push()

# Obtener muestra de transacciones
txs = Transaction.query.limit(10).all()

print("=" * 80)
print("VERIFICACIÓN DE COMISIONES EN TRANSACCIONES")
print("=" * 80)

print(f"\nTotal transacciones: {Transaction.query.count()}")
print(f"\nMuestra de 10 transacciones:")
print(f"{'Tipo':<8} {'Símbolo':<20} {'Commission':>12} {'Fees':>12} {'Tax':>12}")
print("-" * 80)

for t in txs:
    symbol = t.asset.symbol if t.asset else "N/A"
    print(f"{t.transaction_type:<8} {symbol[:20]:<20} {t.commission or 0:>12.2f} {t.fees or 0:>12.2f} {t.tax or 0:>12.2f}")

# Contar cuántas tienen comisiones
with_commission = Transaction.query.filter(Transaction.commission != None, Transaction.commission > 0).count()
with_fees = Transaction.query.filter(Transaction.fees != None, Transaction.fees > 0).count()
with_tax = Transaction.query.filter(Transaction.tax != None, Transaction.tax > 0).count()

print("\n" + "=" * 80)
print(f"📊 ESTADÍSTICAS:")
print(f"   Transacciones con commission > 0: {with_commission}")
print(f"   Transacciones con fees > 0: {with_fees}")
print(f"   Transacciones con tax > 0: {with_tax}")
print("=" * 80)

