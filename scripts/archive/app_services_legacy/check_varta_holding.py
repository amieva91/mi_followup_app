#!/usr/bin/env python3
"""Verificar si VARTA está en los holdings actuales"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import PortfolioHolding, Asset

app = create_app()
app.app_context().push()

# Buscar holdings de VARTA
holdings = PortfolioHolding.query.join(Asset).filter(Asset.symbol.like('%VARTA%')).all()

print("=" * 80)
print("VERIFICACIÓN DE HOLDINGS DE VARTA AG")
print("=" * 80)

if holdings:
    print(f"\n⚠️  VARTA encontrada en holdings ({len(holdings)} entries):")
    for h in holdings:
        print(f"   - {h.asset.symbol}: {h.quantity} unidades")
        print(f"     Account: {h.account.account_name} ({h.account.broker.name})")
        print(f"     Cost: {h.total_cost} {h.asset.currency}")
else:
    print(f"\n✅ VARTA NO está en holdings actuales (correcto, balance = 0)")

# Contar holdings totales
total_holdings = PortfolioHolding.query.count()
print(f"\n📊 Total holdings en BD: {total_holdings}")

# Listar todos los holdings
all_holdings = PortfolioHolding.query.join(Asset).all()
print(f"\n📋 Todos los holdings:")
for h in all_holdings:
    print(f"   • {h.asset.symbol:<15} | Qty: {h.quantity:>10.2f} | {h.asset.currency}")

print("\n" + "=" * 80)

