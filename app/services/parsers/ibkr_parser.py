"""
IBKR Parser - Parse CSV from Interactive Brokers Activity Statement
"""
import csv
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any


class IBKRParser:
    """Parser para archivos CSV de IBKR Activity Statement"""
    
    def __init__(self):
        self.sections = {}
        self.account_info = {}
        self.trades = []
        self.holdings = []
        self.dividends = []
        self.deposits = []
        self.fees = []
        
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parsea un archivo CSV de IBKR
        
        Args:
            file_path: Ruta al archivo CSV
            
        Returns:
            Dict con datos parseados y normalizados
        """
        # Leer y organizar por secciones
        self._read_sections(file_path)
        
        # Parsear cada sección
        self._parse_account_info()
        self._parse_trades()
        self._parse_holdings()
        self._parse_dividends()
        
        # Retornar datos normalizados
        return {
            'broker': 'IBKR',
            'account_info': self.account_info,
            'trades': self.trades,
            'holdings': self.holdings,
            'dividends': self.dividends,
            'deposits': self.deposits,
            'fees': self.fees
        }
    
    def _read_sections(self, file_path: str):
        """Lee el CSV y organiza las líneas por secciones"""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            for row in reader:
                if not row or len(row) < 2:
                    continue
                
                section_name = row[0]
                row_type = row[1]
                
                # Ignorar secciones vacías o headers generales
                if section_name == 'Statement':
                    continue
                
                # Crear sección si no existe
                if section_name not in self.sections:
                    self.sections[section_name] = {
                        'headers': [],
                        'data': []
                    }
                
                # Guardar header o data
                if row_type == 'Header':
                    self.sections[section_name]['headers'] = row[2:]
                elif row_type == 'Data':
                    self.sections[section_name]['data'].append(row[2:])
    
    def _parse_account_info(self):
        """Parsea información de la cuenta"""
        section = self.sections.get('Información sobre la cuenta') or \
                  self.sections.get('Account Information')
        
        if not section:
            return
        
        # En esta sección, cada fila Data tiene [Nombre del campo, Valor]
        for row in section['data']:
            if len(row) >= 2:
                field = row[0]
                value = row[1]
                
                # Mapear campos a nombres en inglés
                field_map = {
                    'Nombre': 'account_holder',
                    'Name': 'account_holder',
                    'Cuenta': 'account_number',
                    'Account': 'account_number',
                    'Tipo de cuenta': 'account_type',
                    'Account Type': 'account_type',
                    'Capacidades de la cuenta': 'account_capabilities',
                    'Account Capabilities': 'account_capabilities',
                    'Divisa base': 'base_currency',
                    'Base Currency': 'base_currency'
                }
                
                english_field = field_map.get(field, field.lower().replace(' ', '_'))
                self.account_info[english_field] = value
    
    def _parse_trades(self):
        """Parsea las operaciones/trades"""
        section = self.sections.get('Operaciones') or \
                  self.sections.get('Trades')
        
        if not section or not section['headers']:
            return
        
        headers = section['headers']
        
        for row in section['data']:
            if len(row) < len(headers):
                continue
            
            # Crear dict con headers
            trade_dict = dict(zip(headers, row))
            
            # Filtrar solo órdenes reales (no subtotales ni totales)
            discriminator = trade_dict.get('DataDiscriminator', '')
            if discriminator != 'Order':
                continue
            
            # Extraer información relevante
            try:
                trade = {
                    'asset_type': trade_dict.get('Categoría de activo', trade_dict.get('Asset Category', '')),
                    'currency': trade_dict.get('Divisa', trade_dict.get('Currency', '')),
                    'symbol': trade_dict.get('Símbolo', trade_dict.get('Symbol', '')),
                    'date_time': self._parse_datetime(trade_dict.get('Fecha/Hora', trade_dict.get('Date/Time', ''))),
                    'quantity': self._parse_decimal(trade_dict.get('Cantidad', trade_dict.get('Quantity', '0'))),
                    'price': self._parse_decimal(trade_dict.get('Precio trans.', trade_dict.get('T. Price', '0'))),
                    'amount': self._parse_decimal(trade_dict.get('Productos', trade_dict.get('Proceeds', '0'))),
                    'commission': self._parse_decimal(trade_dict.get('Tarifa/com.', trade_dict.get('Comm/Fee', '0'))),
                    'realized_pl': self._parse_decimal(trade_dict.get('PyG realizadas', trade_dict.get('Realized P/L', '0'))),
                    'code': trade_dict.get('Código', trade_dict.get('Code', ''))
                }
                
                # Determinar si es compra o venta
                qty = trade['quantity']
                if qty > 0:
                    trade['transaction_type'] = 'BUY'
                elif qty < 0:
                    trade['transaction_type'] = 'SELL'
                    trade['quantity'] = abs(qty)
                else:
                    continue
                
                self.trades.append(trade)
                
            except Exception as e:
                print(f"Error parseando trade: {e}")
                continue
    
    def _parse_holdings(self):
        """Parsea las posiciones abiertas/holdings"""
        section = self.sections.get('Posiciones abiertas') or \
                  self.sections.get('Open Positions')
        
        if not section or not section['headers']:
            return
        
        headers = section['headers']
        
        for row in section['data']:
            if len(row) < len(headers):
                continue
            
            holding_dict = dict(zip(headers, row))
            
            # Filtrar solo Summary (no totales)
            discriminator = holding_dict.get('DataDiscriminator', '')
            if discriminator != 'Summary':
                continue
            
            try:
                holding = {
                    'asset_type': holding_dict.get('Categoría de activo', holding_dict.get('Asset Category', '')),
                    'currency': holding_dict.get('Divisa', holding_dict.get('Currency', '')),
                    'symbol': holding_dict.get('Símbolo', holding_dict.get('Symbol', '')),
                    'quantity': self._parse_decimal(holding_dict.get('Cantidad', holding_dict.get('Quantity', '0'))),
                    'cost_price': self._parse_decimal(holding_dict.get('Precio de coste', holding_dict.get('Cost Price', '0'))),
                    'cost_basis': self._parse_decimal(holding_dict.get('Base de coste', holding_dict.get('Cost Basis', '0'))),
                    'current_price': self._parse_decimal(holding_dict.get('Precio de cierre', holding_dict.get('Close Price', '0'))),
                    'current_value': self._parse_decimal(holding_dict.get('Valor', holding_dict.get('Value', '0'))),
                    'unrealized_pl': self._parse_decimal(holding_dict.get('PyG no realizadas', holding_dict.get('Unreal P/L', '0'))),
                    'code': holding_dict.get('Código', holding_dict.get('Code', ''))
                }
                
                if holding['quantity'] > 0:
                    self.holdings.append(holding)
                    
            except Exception as e:
                print(f"Error parseando holding: {e}")
                continue
    
    def _parse_dividends(self):
        """Parsea los dividendos"""
        section = self.sections.get('Dividendos') or \
                  self.sections.get('Dividends')
        
        if not section or not section['headers']:
            return
        
        headers = section['headers']
        
        for row in section['data']:
            if len(row) < len(headers):
                continue
            
            dividend_dict = dict(zip(headers, row))
            
            # Ignorar líneas de Total
            if 'Total' in dividend_dict.get('Divisa', '') or \
               'Total' in dividend_dict.get('Currency', ''):
                continue
            
            try:
                # Extraer símbolo de la descripción
                description = dividend_dict.get('Descripción', dividend_dict.get('Description', ''))
                symbol = self._extract_symbol_from_description(description)
                
                dividend = {
                    'currency': dividend_dict.get('Divisa', dividend_dict.get('Currency', '')),
                    'date': self._parse_date(dividend_dict.get('Fecha', dividend_dict.get('Date', ''))),
                    'description': description,
                    'symbol': symbol,
                    'amount': self._parse_decimal(dividend_dict.get('Cantidad', dividend_dict.get('Amount', '0')))
                }
                
                if dividend['amount'] > 0:
                    self.dividends.append(dividend)
                    
            except Exception as e:
                print(f"Error parseando dividendo: {e}")
                continue
    
    # Helper methods
    
    def _parse_decimal(self, value: str) -> Decimal:
        """Convierte string a Decimal, manejando formatos variados"""
        if not value or value.strip() in ['', '--', 'N/A']:
            return Decimal('0')
        
        # Limpiar el string
        value = value.strip().replace(',', '').replace(' ', '')
        
        try:
            return Decimal(value)
        except:
            return Decimal('0')
    
    def _parse_datetime(self, value: str) -> str:
        """Parsea fecha/hora de IBKR al formato ISO"""
        if not value or value.strip() == '':
            return None
        
        try:
            # Formato: "2024-04-25, 11:11:05"
            dt = datetime.strptime(value, "%Y-%m-%d, %H:%M:%S")
            return dt.isoformat()
        except:
            return value
    
    def _parse_date(self, value: str) -> str:
        """Parsea fecha de IBKR al formato ISO"""
        if not value or value.strip() == '':
            return None
        
        try:
            # Formato: "2024-07-18"
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.date().isoformat()
        except:
            return value
    
    def _extract_symbol_from_description(self, description: str) -> str:
        """Extrae el símbolo de la descripción del dividendo"""
        if not description:
            return ''
        
        # El símbolo suele estar al inicio, seguido de un paréntesis
        # Ejemplo: "9997 (KYG5215A1004) Dividendo..."
        parts = description.split('(')
        if parts:
            return parts[0].strip()
        
        return ''

