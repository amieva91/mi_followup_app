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
        
        Formato esperado:
        Fecha,Hora,Producto,ISIN,Bolsa de,Centro de,Número,Precio,,Valor local,,Valor,,Tipo de cambio,Costes de transacción,,Total,,ID Orden
        
        Args:
            file_path: Ruta al archivo CSV
            
        Returns:
            Dict con datos parseados y normalizados
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
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
    
    def _process_row(self, row: Dict[str, str]):
        """Procesa una fila del CSV de Transacciones"""
        # Número = cantidad (positivo = compra, negativo = venta)
        numero_str = row.get('Número', '0').replace(',', '.')
        try:
            quantity = float(numero_str)
        except:
            return
        
        if quantity == 0:
            return
        
        # Extraer datos básicos
        fecha = row.get('Fecha', '')
        hora = row.get('Hora', '')
        symbol = row.get('Producto', '').strip()
        isin = row.get('ISIN', '').strip()
        
        # Precio: puede estar en múltiples columnas dependiendo del formato
        # El CSV tiene: Precio,,[Divisa],Valor local,,[Divisa]...
        # Necesitamos encontrar el precio y su divisa
        precio_str = ''
        precio_divisa = ''
        
        # Buscar en las columnas
        cols = list(row.keys())
        for i, col in enumerate(cols):
            if col == 'Precio':
                precio_str = row[col]
                # La divisa está en la siguiente columna no vacía
                if i+1 < len(cols):
                    next_col = cols[i+1]
                    if next_col and not next_col.startswith('Unnamed'):
                        precio_divisa = row[next_col]
                    elif i+2 < len(cols):
                        precio_divisa = row[cols[i+2]]
                break
        
        # Limpiar precio (convertir coma a punto)
        if precio_str:
            precio_str = precio_str.replace('.', '').replace(',', '.')
        
        try:
            price = Decimal(precio_str) if precio_str else Decimal('0')
        except:
            price = Decimal('0')
        
        # Extraer comisión de "Costes de transacción"
        commission = Decimal('0')
        commission_str = ''
        for i, col in enumerate(cols):
            if 'Costes de transacción' in col or col == 'Costes de transacción':
                commission_str = row.get(col, '0')
                break
        
        if commission_str:
            # Limpiar y convertir (formato: "-2,00" o "2,00")
            commission_str = commission_str.replace('.', '').replace(',', '.').replace('-', '')
            try:
                commission = Decimal(commission_str) if commission_str else Decimal('0')
            except:
                commission = Decimal('0')
        
        # Crear trade
        trade = {
            'transaction_type': 'BUY' if quantity > 0 else 'SELL',
            'symbol': symbol,
            'isin': isin,
            'date': self._parse_date(fecha),
            'date_time': self._parse_datetime(fecha, hora),
            'quantity': abs(int(quantity)),  # Convertir a positivo
            'price': price,
            'currency': precio_divisa if precio_divisa else 'EUR',
            'commission': commission,  # Añadir comisión
            'order_id': row.get('ID Orden', '').strip(),
            'description': f"{'Compra' if quantity > 0 else 'Venta'} {abs(quantity)} {symbol}"
        }
        
        # Calcular monto total
        trade['amount'] = abs(price * Decimal(str(abs(quantity))))
        
        self.trades.append(trade)
    
    def _calculate_holdings(self):
        """Calcula holdings actuales desde las transacciones usando ISIN como key"""
        for trade in self.trades:
            symbol = trade['symbol']
            isin = trade['isin']
            
            # Usar ISIN como key principal (nunca cambia)
            key = isin if isin else symbol
            
            if key not in self.holdings:
                self.holdings[key] = {
                    'symbol': symbol,
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

