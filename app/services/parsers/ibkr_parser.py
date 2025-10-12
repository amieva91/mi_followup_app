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
        self.symbol_isin_map = {}  # Mapeo símbolo -> ISIN
        self.instrument_info = {}  # Mapeo símbolo -> {isin, name, exchange, type}
    
    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """
        Normaliza símbolos de IBKR eliminando sufijos comunes.
        
        IBKR a veces añade sufijos a los símbolos (ej: IGC -> IGCl, NKR -> NKRo)
        que causan problemas al matching de compras/ventas.
        
        Args:
            symbol: Símbolo original del CSV
            
        Returns:
            Símbolo normalizado sin sufijos
        """
        if not symbol:
            return symbol
        
        # Lista de sufijos conocidos de IBKR
        # 'l' = listed, 'o' = old/option, etc.
        suffixes = ['l', 'o']
        
        # Ignorar símbolos de forex (contienen '.')
        if '.' in symbol:
            return symbol
        
        # Si termina en un sufijo de 1 caracter, verificar si es un sufijo conocido
        if len(symbol) > 1 and symbol[-1].lower() in suffixes:
            return symbol[:-1]
        
        return symbol
        
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
        self._parse_financial_instruments()  # Primero ISINs
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
    
    def _parse_financial_instruments(self):
        """Parsea información de instrumentos financieros para extraer ISINs, nombre, exchange, tipo"""
        section = self.sections.get('Información de instrumento financiero') or \
                  self.sections.get('Financial Instrument Information')
        
        if not section or not section['headers']:
            return
        
        headers = section['headers']
        
        for row in section['data']:
            if len(row) < len(headers):
                continue
            
            instrument_dict = dict(zip(headers, row))
            
            try:
                # Extraer datos (soporte español e inglés)
                raw_symbol = instrument_dict.get('Símbolo', instrument_dict.get('Symbol', ''))
                normalized_symbol = self._normalize_symbol(raw_symbol)
                isin = instrument_dict.get('Id. de seguridad', instrument_dict.get('Security ID', ''))
                name = instrument_dict.get('Descripción', instrument_dict.get('Description', ''))
                exchange = instrument_dict.get('Merc. de cotización', instrument_dict.get('Listing Exch', ''))
                tipo = instrument_dict.get('Tipo', instrument_dict.get('Type', ''))
                
                # Determinar asset_type: ETF o Stock
                if 'ETF' in tipo.upper():
                    asset_type = 'ETF'
                else:
                    asset_type = 'Stock'
                
                if normalized_symbol and isin:
                    # Guardar mapeo completo
                    self.instrument_info[normalized_symbol] = {
                        'isin': isin,
                        'name': name,
                        'exchange': exchange,
                        'asset_type': asset_type
                    }
                    
                    # Mantener el mapeo simple para compatibilidad
                    self.symbol_isin_map[normalized_symbol] = isin
                    
                    # También guardar el símbolo sin normalizar
                    if raw_symbol != normalized_symbol:
                        self.instrument_info[raw_symbol] = self.instrument_info[normalized_symbol]
                        self.symbol_isin_map[raw_symbol] = isin
                        
            except Exception as e:
                print(f"Error parseando instrumento: {e}")
                continue
    
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
                raw_symbol = trade_dict.get('Símbolo', trade_dict.get('Symbol', ''))
                normalized_symbol = self._normalize_symbol(raw_symbol)
                
                # Obtener info completa del instrumento
                instrument = self.instrument_info.get(normalized_symbol, {})
                isin = instrument.get('isin', '')
                name = instrument.get('name', normalized_symbol)
                exchange = instrument.get('exchange', '')
                
                # Para asset_type: priorizar CSV (puede ser "Fórex"), luego instrument_info, luego 'Stock'
                asset_type_csv = trade_dict.get('Categoría de activo', trade_dict.get('Asset Category', ''))
                if asset_type_csv:
                    asset_type = asset_type_csv
                else:
                    asset_type = instrument.get('asset_type', 'Stock')
                
                trade = {
                    'asset_type': asset_type,
                    'currency': trade_dict.get('Divisa', trade_dict.get('Currency', '')),
                    'symbol': normalized_symbol,
                    'isin': isin,
                    'name': name,
                    'exchange': exchange,
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
                raw_symbol = holding_dict.get('Símbolo', holding_dict.get('Symbol', ''))
                normalized_symbol = self._normalize_symbol(raw_symbol)
                
                # Obtener info completa del instrumento
                instrument = self.instrument_info.get(normalized_symbol, {})
                isin = instrument.get('isin', '')
                name = instrument.get('name', normalized_symbol)
                exchange = instrument.get('exchange', '')
                asset_type = instrument.get('asset_type', 'Stock')
                
                holding = {
                    'asset_type': asset_type,
                    'currency': holding_dict.get('Divisa', holding_dict.get('Currency', '')),
                    'symbol': normalized_symbol,
                    'isin': isin,
                    'name': name,
                    'exchange': exchange,
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
        """
        Parsea dividendos con conversión EUR y agrupación inteligente
        
        ESTRUCTURA DEL CSV:
        row[0] = Divisa (HKD, USD, Total, Total en EUR)
        row[1] = Fecha
        row[2] = Descripción
        row[3] = Cantidad
        
        Lógica:
        1. Agrupar por moneda (la sección viene ordenada así)
        2. Para cada moneda, extraer: dividendos individuales + Total + Total en EUR
        3. Calcular exchange_rate = total_eur / total_local
        4. Agrupar dividendos por (fecha + símbolo)
        5. Aplicar exchange_rate a cada grupo
        """
        section = self.sections.get('Dividendos') or \
                  self.sections.get('Dividends')
        
        if not section or not section['data']:
            return
        
        from collections import defaultdict
        
        currency_groups = []  # [(currency, [dividends], total_local, total_eur)]
        current_currency = None
        current_dividends = []
        total_local = Decimal('0')
        total_eur = Decimal('0')
        
        for row in section['data']:
            if len(row) < 4:
                continue
            
            currency_field = row[0]  # Divisa
            date_field = row[1]      # Fecha
            description = row[2]     # Descripción
            amount_str = row[3]      # Cantidad
            
            # Detectar dividendo individual (con moneda real: HKD, USD, etc.)
            if currency_field and currency_field not in ['Total', 'Total en EUR', 'Total Dividendos en EUR'] and date_field:
                # Si cambia la moneda, guardar el grupo anterior
                if current_currency and current_currency != currency_field:
                    currency_groups.append((current_currency, current_dividends, total_local, total_eur))
                    current_dividends = []
                    total_local = Decimal('0')
                    total_eur = Decimal('0')
                
                current_currency = currency_field
                
                # Extraer dividendo individual
                try:
                    raw_symbol, isin = self._extract_symbol_and_isin_from_div_description(description)
                    normalized_symbol = self._normalize_symbol(raw_symbol)
                    
                    dividend = {
                        'currency': currency_field,
                        'date': self._parse_date(date_field),
                        'description': description,
                        'symbol': normalized_symbol,
                        'isin': isin,
                        'amount_local': self._parse_decimal(amount_str)
                    }
                    
                    if dividend['amount_local'] > 0:
                        current_dividends.append(dividend)
                except Exception as e:
                    print(f"Error parseando dividendo individual: {e}")
                    
            # Detectar Total (en moneda local)
            elif currency_field == 'Total' and amount_str:
                total_local = self._parse_decimal(amount_str)
                
            # Detectar Total en EUR
            elif currency_field == 'Total en EUR' and amount_str:
                total_eur = self._parse_decimal(amount_str)
        
        # Guardar el último grupo
        if current_currency and current_dividends:
            currency_groups.append((current_currency, current_dividends, total_local, total_eur))
        
        # Paso 2: Procesar cada grupo de moneda
        for currency, dividends_list, total_local, total_eur in currency_groups:
            # Calcular exchange_rate
            if total_local > 0 and total_eur > 0:
                exchange_rate = total_eur / total_local
            else:
                exchange_rate = Decimal('1')  # Fallback
            
            # Agrupar por (fecha + símbolo)
            grouped_dividends = defaultdict(list)
            for div in dividends_list:
                key = (div['date'], div['symbol'])
                grouped_dividends[key].append(div)
            
            # Crear dividendos finales
            for (date, symbol), divs in grouped_dividends.items():
                # Sumar montos locales del mismo día/símbolo
                amount_local_total = sum(d['amount_local'] for d in divs)
                
                # Convertir a EUR
                amount_eur = amount_local_total * exchange_rate
                
                # Obtener info del instrumento
                instrument = self.instrument_info.get(symbol, {})
                isin = divs[0]['isin'] or instrument.get('isin', '')
                name = instrument.get('name', symbol)
                exchange = instrument.get('exchange', '')
                asset_type = instrument.get('asset_type', 'Stock')
                
                final_dividend = {
                    'currency': 'EUR',  # Moneda convertida
                    'currency_original': currency,  # Moneda local
                    'date': date,
                    'symbol': symbol,
                    'isin': isin,
                    'name': name,
                    'exchange': exchange,
                    'asset_type': asset_type,
                    'amount': float(amount_eur),  # EUR
                    'amount_original': float(amount_local_total),  # Moneda local
                    'description': f"Dividendo {symbol}"
                }
                
                self.dividends.append(final_dividend)
    
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
    
    def _extract_symbol_and_isin_from_div_description(self, description: str) -> tuple:
        """
        Extrae símbolo e ISIN de la descripción del dividendo
        
        Formato esperado: "SYMBOL(ISIN) ..."
        Ejemplo: "9997(KYG5215A1004) Dividendo en efectivo HKD 0.2613 por acción (Dividendo ordinario)"
        
        Returns:
            (symbol, isin)
        """
        import re
        
        if not description:
            return ('', '')
        
        # Patrón: SYMBOL(ISIN)
        # El ISIN está entre paréntesis después del símbolo
        pattern = r'^([^\(]+)\(([A-Z0-9]+)\)'
        match = re.match(pattern, description)
        
        if match:
            symbol = match.group(1).strip()
            isin = match.group(2).strip()
            return (symbol, isin)
        
        # Fallback: extraer solo símbolo
        symbol = self._extract_symbol_from_description(description)
        return (symbol, '')

