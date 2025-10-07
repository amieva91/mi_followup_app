"""
FIFO Calculator - Cálculo robusto de holdings usando FIFO real con lotes
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any
from collections import deque


class FIFOLot:
    """Representa un lote de compra individual"""
    def __init__(self, quantity: float, price: float, date: datetime, total_cost: float):
        self.quantity = Decimal(str(quantity))
        self.price = Decimal(str(price))
        self.date = date
        self.total_cost = Decimal(str(total_cost))
    
    def __repr__(self):
        return f"Lot({self.quantity} @ {self.price} on {self.date.date()})"


class FIFOCalculator:
    """Calculadora FIFO robusta para holdings"""
    
    def __init__(self, symbol: str = "Unknown"):
        self.symbol = symbol
        self.lots: deque = deque()  # Cola FIFO de lotes de compra
        self.first_purchase_date = None
        self.last_transaction_date = None
    
    def add_buy(self, quantity: float, price: float, date: datetime, total_cost: float):
        """Añade una compra como un nuevo lote"""
        lot = FIFOLot(quantity, price, date, total_cost)
        self.lots.append(lot)
        
        if self.first_purchase_date is None or date < self.first_purchase_date:
            self.first_purchase_date = date
        
        self.last_transaction_date = date
    
    def add_sell(self, quantity: float, date: datetime) -> Decimal:
        """
        Procesa una venta consumiendo lotes FIFO.
        Retorna el coste de las acciones vendidas (para P&L).
        """
        remaining_to_sell = Decimal(str(quantity))
        total_cost_sold = Decimal('0')
        
        while remaining_to_sell > 0 and len(self.lots) > 0:
            oldest_lot = self.lots[0]
            
            if oldest_lot.quantity <= remaining_to_sell:
                # Consumir el lote completo
                remaining_to_sell -= oldest_lot.quantity
                total_cost_sold += oldest_lot.total_cost
                self.lots.popleft()  # Eliminar lote consumido
            else:
                # Consumir parcialmente el lote
                sold_from_lot = remaining_to_sell
                cost_per_share = oldest_lot.total_cost / oldest_lot.quantity
                cost_sold_from_lot = cost_per_share * sold_from_lot
                
                oldest_lot.quantity -= sold_from_lot
                oldest_lot.total_cost -= cost_sold_from_lot
                
                total_cost_sold += cost_sold_from_lot
                remaining_to_sell = Decimal('0')
        
        self.last_transaction_date = date
        
        if remaining_to_sell > 0:
            print(f"⚠️  Advertencia ({self.symbol}): Se intentó vender {remaining_to_sell} más de lo disponible en fecha {date}")
        
        return total_cost_sold
    
    def get_current_position(self) -> Dict[str, Any]:
        """Obtiene la posición actual calculada desde los lotes"""
        if not self.lots:
            return {
                'quantity': 0,
                'total_cost': 0,
                'average_buy_price': 0,
                'first_purchase_date': None,
                'last_transaction_date': self.last_transaction_date
            }
        
        total_quantity = sum(lot.quantity for lot in self.lots)
        total_cost = sum(lot.total_cost for lot in self.lots)
        
        return {
            'quantity': float(total_quantity),
            'total_cost': float(total_cost),
            'average_buy_price': float(total_cost / total_quantity) if total_quantity > 0 else 0,
            'first_purchase_date': self.first_purchase_date,
            'last_transaction_date': self.last_transaction_date
        }
    
    def is_closed(self) -> bool:
        """Verifica si la posición está cerrada (vendida completamente)"""
        return len(self.lots) == 0
    
    def __repr__(self):
        pos = self.get_current_position()
        return f"FIFOCalculator({pos['quantity']} lots, qty={pos['quantity']}, avg={pos['average_buy_price']:.2f})"


def calculate_holdings_fifo(transactions: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Calcula holdings usando FIFO robusto desde una lista de transacciones.
    
    Args:
        transactions: Lista de transacciones ordenadas por fecha
        
    Returns:
        Dict con asset_id como key y datos del holding como value
    """
    calculators = {}  # asset_id -> FIFOCalculator
    
    for tx in transactions:
        asset_id = tx['asset_id']
        
        # Inicializar calculadora si no existe
        if asset_id not in calculators:
            calculators[asset_id] = FIFOCalculator()
        
        calc = calculators[asset_id]
        
        if tx['transaction_type'] == 'BUY':
            calc.add_buy(
                quantity=tx['quantity'],
                price=tx['price'],
                date=tx['date'],
                total_cost=tx['amount']
            )
        elif tx['transaction_type'] == 'SELL':
            calc.add_sell(
                quantity=tx['quantity'],
                date=tx['date']
            )
    
    # Convertir calculadoras a holdings
    holdings = {}
    for asset_id, calc in calculators.items():
        if not calc.is_closed():
            holdings[asset_id] = calc.get_current_position()
    
    return holdings

