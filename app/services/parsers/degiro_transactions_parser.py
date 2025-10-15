"""
DeGiro Transactions Parser - Parse CSV from DeGiro Transactions Report
Este es el formato "Transacciones" de DeGiro, más completo que el "Estado de Cuenta"
"""
import csv
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any


class DeGiroTransactionsParser:
    """Parser para el reporte de Transacciones de DeGiro (más completo que Estado de Cuenta)"""
    
    def __init__(self):
        self.account_info = {}
        self.trades = []
        self.holdings = {}
        
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parsea un archivo CSV de Transacciones de DeGiro
        
        Formato esperado (por índice de columna):
        0: Fecha
        1: Hora
        2: Producto
        3: ISIN
        4: Bolsa de
        5: Centro de
        6: Número
        7: Precio
        8: [MONEDA] - sin nombre en header
        9: Valor local
        10: [MONEDA] - sin nombre en header
        ...
        
        Args:
            file_path: Ruta al archivo CSV
            
        Returns:
            Dict con datos parseados y normalizados
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # Leer header pero no lo usamos
            
            for row in reader:
                if len(row) < 9:  # Validar que tenga suficientes columnas
                    continue
                self._process_row(row)
        
        # Calcular holdings desde trades
        self._calculate_holdings()
        
        # Retornar datos normalizados
        return {
            'broker': 'DEGIRO',
            'account_info': self.account_info,
            'trades': self.trades,
            'holdings': list(self.holdings.values()),
            'dividends': [],  # Los dividendos no están en este CSV
            'deposits': [],
            'fees': [],
            'fx_transactions': []
        }
    
    def _process_row(self, row: List[str]):
        """
        Procesa una fila del CSV de Transacciones usando índices de columna
        
        Índices:
        0: Fecha, 1: Hora, 2: Producto, 3: ISIN, 4: Bolsa, 5: Centro,
        6: Número, 7: Precio, 8: [MONEDA], 9: Valor local, 10: [MONEDA],
        11: Valor, 12: [MONEDA EUR], 13: Tipo cambio, 14: Costes, 15: [MONEDA],
        16: Total, 17: [MONEDA EUR], 18: ID Orden
        """
        try:
            # Columna 6: Número (cantidad)
            numero_str = row[6].replace(',', '.') if len(row) > 6 else '0'
            quantity = float(numero_str)
        except:
            return
        
        if quantity == 0:
            return
        
        # Extraer datos básicos
        fecha = row[0] if len(row) > 0 else ''
        hora = row[1] if len(row) > 1 else ''
        # row[2] es el nombre del producto, NO un ticker - DeGiro no proporciona tickers
        product_name = row[2].strip() if len(row) > 2 else ''
        isin = row[3].strip() if len(row) > 3 else ''
        symbol = ''  # DeGiro no proporciona tickers/symbols en sus CSVs
        
        # Columna 7: Precio
        precio_str = row[7] if len(row) > 7 else '0'
        # Columna 8: MONEDA (¡aquí está la moneda correcta!)
        precio_divisa = row[8].strip() if len(row) > 8 else 'EUR'
        
        # Limpiar precio (convertir coma a punto, quitar separadores de miles)
        precio_str = precio_str.replace('.', '').replace(',', '.')
        
        try:
            price = Decimal(precio_str) if precio_str else Decimal('0')
        except:
            price = Decimal('0')
        
        # Columna 14: Costes de transacción (comisión)
        commission = Decimal('0')
        if len(row) > 14:
            commission_str = row[14].replace(',', '.').replace('-', '')
            try:
                commission = Decimal(commission_str) if commission_str else Decimal('0')
            except:
                commission = Decimal('0')
        
        # Columna 18: ID Orden
        order_id = row[18].strip() if len(row) > 18 else ''
        
        # Crear trade
        trade = {
            'transaction_type': 'BUY' if quantity > 0 else 'SELL',
            'symbol': symbol,  # Vacío para DeGiro (no proporciona tickers)
            'name': product_name,  # Nombre del producto para identificación
            'isin': isin,
            'date': self._parse_date(fecha),
            'date_time': self._parse_datetime(fecha, hora),
            'quantity': abs(int(quantity)),
            'price': price,
            'currency': precio_divisa,  # ¡Ahora lee la columna correcta!
            'commission': commission,
            'order_id': order_id,
            'description': f"{'Compra' if quantity > 0 else 'Venta'} {abs(int(quantity))} {product_name}"
        }
        
        # Calcular monto total
        trade['amount'] = abs(price * Decimal(str(abs(quantity))))
        
        self.trades.append(trade)
    
    def _calculate_holdings(self):
        """Calcula holdings actuales desde las transacciones usando ISIN como key"""
        for trade in self.trades:
            symbol = trade['symbol']
            name = trade.get('name', '')
            isin = trade['isin']
            
            # Usar ISIN como key principal (nunca cambia)
            key = isin if isin else symbol
            
            if key not in self.holdings:
                self.holdings[key] = {
                    'symbol': symbol,
                    'name': name,  # Incluir nombre del producto
                    'isin': isin,
                    'currency': trade['currency'],
                    'quantity': 0,
                    'total_cost': Decimal('0'),
                    'average_buy_price': Decimal('0')
                }
            
            holding = self.holdings[key]
            
            if trade['transaction_type'] == 'BUY':
                # Actualizar cantidad y coste
                new_quantity = holding['quantity'] + trade['quantity']
                new_cost = holding['total_cost'] + (trade['price'] * trade['quantity'])
                
                holding['quantity'] = new_quantity
                holding['total_cost'] = new_cost
                holding['average_buy_price'] = new_cost / new_quantity if new_quantity > 0 else Decimal('0')
                
            elif trade['transaction_type'] == 'SELL':
                # Reducir cantidad
                holding['quantity'] -= trade['quantity']
                
                # Reducir coste proporcional (FIFO simplificado)
                if holding['quantity'] > 0:
                    cost_per_share = holding['total_cost'] / (holding['quantity'] + trade['quantity'])
                    holding['total_cost'] -= cost_per_share * trade['quantity']
                else:
                    holding['total_cost'] = Decimal('0')
        
        # Eliminar holdings con cantidad <= 0
        self.holdings = {k: v for k, v in self.holdings.items() if v['quantity'] > 0}
    
    # Helper methods
    
    def _parse_date(self, date_str: str) -> str:
        """Parsea fecha DD-MM-YYYY a YYYY-MM-DD"""
        if not date_str:
            return ''
        try:
            # Formato: DD-MM-YYYY
            dt = datetime.strptime(date_str, '%d-%m-%Y')
            return dt.strftime('%Y-%m-%d')
        except:
            return date_str
    
    def _parse_datetime(self, date_str: str, time_str: str) -> str:
        """Parsea fecha y hora a formato ISO"""
        if not date_str:
            return ''
        try:
            # Formato: DD-MM-YYYY HH:MM
            dt_str = f"{date_str} {time_str if time_str else '00:00'}"
            dt = datetime.strptime(dt_str, '%d-%m-%Y %H:%M')
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except:
            return date_str


# Factory function para mantener compatibilidad
def create_parser() -> DeGiroTransactionsParser:
    """Crea una instancia del parser"""
    return DeGiroTransactionsParser()

