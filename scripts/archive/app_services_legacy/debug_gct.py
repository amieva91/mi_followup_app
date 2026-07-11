"""
Debug de transacciones de GCT para identificar el problema
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import Transaction, Asset
from datetime import datetime

app = create_app()

with app.app_context():
    # Buscar el asset GCT
    gct = Asset.query.filter_by(symbol='GCT').first()
    
    if not gct:
        print("❌ No se encontró el asset GCT")
        exit(1)
    
    print(f"✅ Asset encontrado: {gct.symbol} (ID: {gct.id})")
    print(f"   ISIN: {gct.isin}")
    print(f"   Nombre: {gct.name}")
    print(f"   Divisa: {gct.currency}")
    
    # Obtener todas las transacciones de GCT ordenadas por fecha
    transactions = Transaction.query.filter_by(
        asset_id=gct.id
    ).order_by(Transaction.transaction_date).all()
    
    print(f"\n📝 Transacciones de GCT (total: {len(transactions)}):\n")
    
    balance = 0
    for i, tx in enumerate(transactions, 1):
        date_str = tx.transaction_date.strftime('%Y-%m-%d %H:%M:%S')
        
        if tx.transaction_type == 'BUY':
            balance += tx.quantity
            sign = '+'
            color = '🟢'
        elif tx.transaction_type == 'SELL':
            balance -= tx.quantity
            sign = '-'
            color = '🔴'
        else:
            sign = ' '
            color = '🔵'
        
        print(f"{i:2d}. {date_str} | {color} {tx.transaction_type:4s} | {sign}{tx.quantity:6.0f} @ {tx.price:8.2f} {tx.currency} | Balance: {balance:6.0f}")
        
        # Advertir si el balance se vuelve negativo
        if balance < 0:
            print(f"    ⚠️  BALANCE NEGATIVO: {balance}")
    
    print(f"\n📊 Resumen:")
    print(f"   Balance final: {balance}")
    
    if balance < 0:
        print(f"   ❌ PROBLEMA: Balance negativo indica que se vendió más de lo comprado")
    elif balance == 0:
        print(f"   ✅ Posición cerrada correctamente")
    else:
        print(f"   ✅ Posición abierta con {balance} acciones")

