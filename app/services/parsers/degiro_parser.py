"""
DeGiro Parser - Parse CSV from DeGiro Account Statement
"""
import csv
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any


class DeGiroParser:
    """Parser para archivos CSV de DeGiro Estado de Cuenta"""
    
    # Tipos de transacción detectados
    TRANSACTION_TYPES = {
        'Compra': 'BUY',
        'Venta': 'SELL',
        'Dividendo': 'DIVIDEND',
        'Retención del dividendo': 'TAX',
        'Costes de transacción': 'FEE',
        'Comisión': 'FEE',
        'Interés': 'INTEREST',
        'Flatex Interest': 'INTEREST',
        'Ingreso Cambio de Divisa': 'FX_IN',
        'Retirada Cambio de Divisa': 'FX_OUT',
        'flatex Withdrawal': 'WITHDRAWAL',
        'Processed Flatex Withdrawal': 'WITHDRAWAL_PROCESSED',
        'Degiro Cash Sweep': 'CASH_SWEEP'
    }
    
    def __init__(self):
        self.account_info = {}
        self.trades = []
        self.holdings = {}  # Se calcularán desde trades
        self.dividends = []
        self.deposits = []
        self.fees = []
        self.fx_transactions = []
        
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parsea un archivo CSV de DeGiro
        
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
            'dividends': self.dividends,
            'deposits': self.deposits,
            'fees': self.fees,
            'fx_transactions': self.fx_transactions
        }
    
    def _process_row(self, row: Dict[str, str]):
        """Procesa una fila del CSV"""
        description = row.get('Descripción', '').strip()
        
        # Detectar tipo de transacción
        # IMPORTANTE: El CSV "Estado de Cuenta" NO debe importar compras/ventas
        # porque ya están en el CSV "Transacciones" (más completo y preciso)
        # Solo procesamos: dividendos, comisiones generales, depósitos, cambios FX
        
        # if 'Compra' in description or 'Venta' in description:
        #     self._process_trade(row)
        # ↑ DESHABILITADO: Las compras/ventas deben venir del CSV "Transacciones"
        
        if description == 'Dividendo':
            self._process_dividend(row)
        elif 'Retención del dividendo' in description or description == 'Retención del dividendo':
            self._process_dividend_tax(row)
        elif 'Costes de transacción' in description or 'Comisión' in description:
            # IMPORTANTE: Filtrar "Costes de transacción" que hacen referencia a un asset
            # porque ya están incluidos en el CSV de Transacciones
            producto = row.get('Producto', '').strip()
            
            # Solo procesar comisiones si:
            # 1. NO es "Costes de transacción" con producto (duplicado del CSV Transacciones)
            # 2. O SI es otro tipo de comisión (conectividad, etc.)
            if 'Costes de transacción' in description and producto:
                # Es una comisión de transacción específica → IGNORAR (duplicado)
                pass
            else:
                # Es una comisión general (conectividad, etc.) → REGISTRAR
                self._process_fee(row)
        elif 'Cambio de Divisa' in description:
            self._process_fx(row)
    
    def _process_trade(self, row: Dict[str, str]):
        """Procesa una compra o venta"""
        description = row.get('Descripción', '')
        
        # Extraer información de la descripción
        # Formato: "Compra 60 ADR on Alibaba Group Holding@160,97 USD (US01609W1027)"
        match = re.match(r'(Compra|Venta)\s+(\d+)\s+(.+?)@([\d,\.]+)\s+(\w+)', description)
        
        if not match:
            return
        
        action, quantity, product, price, currency = match.groups()
        
        # Limpiar precio (convertir coma a punto, eliminar separador de miles)
        price = price.replace('.', '').replace(',', '.')
        
        try:
            quantity_num = int(quantity)
            price_decimal = Decimal(price)
        except:
            # Si no se puede parsear, saltar esta transacción
            return
        
        # ISIN puede estar en la columna o en paréntesis en descripción
        isin = row.get('ISIN', '').strip()
        if not isin:
            # Extraer de descripción si está en paréntesis
            isin_match = re.search(r'\(([A-Z0-9]{12})\)', description)
            if isin_match:
                isin = isin_match.group(1)
        
        trade = {
            'transaction_type': 'BUY' if action == 'Compra' else 'SELL',
            'symbol': row.get('Producto', product).strip(),
            'isin': isin,
            'date': self._parse_date(row.get('Fecha', '')),
            'date_time': self._parse_datetime(row.get('Fecha', ''), row.get('Hora', '')),
            'quantity': quantity_num,
            'price': price_decimal,
            'currency': currency,
            'order_id': row.get('ID Orden', '').strip(),
            'description': description
        }
        
        # Calcular monto total (Variación)
        variation = self._parse_decimal(row.get('Variación', '0'))
        trade['amount'] = abs(variation)
        
        # Para ventas, la cantidad debe ser positiva en nuestro sistema
        if trade['transaction_type'] == 'SELL':
            trade['amount'] = variation  # Ya es positivo para ventas
        
        self.trades.append(trade)
    
    def _process_dividend(self, row: Dict[str, str]):
        """Procesa un dividendo"""
        # IMPORTANTE: En el CSV Estado de Cuenta de DeGiro:
        # - Columna "Variación" contiene la DIVISA (EUR, HKD, USD)
        # - Columna SIN NOMBRE (siguiente a "Variación") contiene el MONTO
        amount_value = Decimal('0')
        currency = row.get('Variación', 'EUR').strip()  # La divisa está en "Variación"
        
        # Buscar la columna sin nombre que tiene el monto
        for key, value in row.items():
            if key == '' and value:  # Columna sin nombre con valor
                amount_value = self._parse_decimal(value)
                break
        
        dividend = {
            'symbol': row.get('Producto', '').strip(),
            'isin': row.get('ISIN', '').strip(),
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': amount_value,
            'currency': currency,
            'description': row.get('Descripción', '').strip()
        }
        
        if dividend['amount'] > 0:
            self.dividends.append(dividend)
    
    def _process_dividend_tax(self, row: Dict[str, str]):
        """Procesa retención de dividendo"""
        # Extraer monto de columna sin nombre (igual que dividendos)
        amount_value = Decimal('0')
        currency = row.get('Variación', 'EUR').strip()
        
        for key, value in row.items():
            if key == '' and value:
                amount_value = self._parse_decimal(value)
                break
        
        # Añadir a dividendos con monto negativo para indicar retención
        tax = {
            'symbol': row.get('Producto', '').strip(),
            'isin': row.get('ISIN', '').strip(),
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': amount_value,  # Ya es negativo del CSV
            'currency': currency,
            'description': 'Retención de impuestos',
            'is_tax': True
        }
        
        self.dividends.append(tax)
    
    def _process_fee(self, row: Dict[str, str]):
        """Procesa comisiones y costes"""
        # Extraer monto de columna sin nombre
        amount_value = Decimal('0')
        currency = row.get('Variación', 'EUR').strip()
        
        for key, value in row.items():
            if key == '' and value:
                amount_value = self._parse_decimal(value)
                break
        
        fee = {
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': abs(amount_value),
            'currency': currency,
            'description': row.get('Descripción', '').strip(),
            'related_symbol': row.get('Producto', '').strip()
        }
        
        self.fees.append(fee)
    
    def _process_fx(self, row: Dict[str, str]):
        """Procesa cambio de divisa"""
        # Extraer monto de columna sin nombre
        amount_value = Decimal('0')
        currency = row.get('Variación', 'EUR').strip()
        
        for key, value in row.items():
            if key == '' and value:
                amount_value = self._parse_decimal(value)
                break
        
        fx = {
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': amount_value,
            'currency': currency,
            'exchange_rate': self._parse_decimal(row.get('Tipo', '0')),
            'description': row.get('Descripción', '').strip()
        }
        
        self.fx_transactions.append(fx)
    
    def _calculate_holdings(self):
        """Calcula holdings actuales desde las transacciones"""
        for trade in self.trades:
            symbol = trade['symbol']
            isin = trade['isin']
            
            # Usar ISIN como key principal (nunca cambia), fallback a símbolo si no hay ISIN
            # Esto asegura que compras/ventas del mismo activo se agrupen correctamente
            # incluso si el nombre del símbolo varía ligeramente
            key = isin if isin else symbol
            
            if key not in self.holdings:
                self.holdings[key] = {
                    'symbol': symbol,  # Guardar el primer símbolo encontrado
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
                
                # Reducir coste proporcional
                if holding['quantity'] > 0:
                    cost_per_share = holding['total_cost'] / (holding['quantity'] + trade['quantity'])
                    holding['total_cost'] -= cost_per_share * trade['quantity']
                else:
                    holding['total_cost'] = Decimal('0')
        
        # Eliminar holdings con cantidad 0
        self.holdings = {k: v for k, v in self.holdings.items() if v['quantity'] > 0}
    
    # Helper methods
    
    def _parse_decimal(self, value: str) -> Decimal:
        """Convierte string a Decimal, manejando formato europeo"""
        if not value or value.strip() in ['', '--', 'N/A']:
            return Decimal('0')
        
        # Limpiar y convertir formato europeo (coma decimal) a punto
        value = value.strip().replace('.', '').replace(',', '.')
        
        try:
            return Decimal(value)
        except:
            return Decimal('0')
    
    def _parse_date(self, date_str: str) -> str:
        """Parsea fecha de DeGiro al formato ISO"""
        if not date_str or date_str.strip() == '':
            return None
        
        try:
            # Formato: "05-10-2025"
            dt = datetime.strptime(date_str.strip(), "%d-%m-%Y")
            return dt.date().isoformat()
        except:
            return date_str
    
    def _parse_datetime(self, date_str: str, time_str: str) -> str:
        """Parsea fecha/hora de DeGiro al formato ISO"""
        if not date_str or date_str.strip() == '':
            return None
        
        try:
            # Formato: "05-10-2025" + "06:30"
            datetime_str = f"{date_str.strip()} {time_str.strip() if time_str else '00:00'}"
            dt = datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")
            return dt.isoformat()
        except:
            return f"{date_str}T{time_str if time_str else '00:00'}"
    
    def _extract_currency(self, row: Dict[str, str]) -> str:
        """Extrae la divisa de las columnas de saldo"""
        # En DeGiro, la divisa está en columnas sin nombre después de Variación y Saldo
        # Intentar obtener de la siguiente columna después de Variación
        for key in row.keys():
            if key.strip() == '' and row[key].strip() in ['EUR', 'USD', 'GBP', 'HKD', 'AUD', 'CAD', 'SGD']:
                return row[key].strip()
        
        # Por defecto EUR
        return 'EUR'

