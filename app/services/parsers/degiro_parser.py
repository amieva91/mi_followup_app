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
        self.withdrawals = []
        self.fees = []
        self.fx_transactions = []
        
        # Para agrupar dividendos con su conversión FX
        self.dividend_fx_map = {}  # {monto_divisa_producto: {'dividend': {...}, 'fx_eur': {...}, 'tax': {...}}}
        self.fx_withdrawals = []  # Todas las "Retirada Cambio de Divisa"
        self.fx_deposits = []  # Todas las "Ingreso Cambio de Divisa" (sin producto)
        
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parsea un archivo CSV de DeGiro
        
        Args:
            file_path: Ruta al archivo CSV
            
        Returns:
            Dict con datos parseados y normalizados
        """
        # Leer CSV con `reader` para acceder por índice (dos columnas sin nombre)
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_reader = csv.reader(f)
            header = next(raw_reader)  # Leer header
            
            # Procesar cada fila
            for raw_values in raw_reader:
                # Crear dict manual con índices correctos
                row = {}
                for i, col_name in enumerate(header):
                    if i < len(raw_values):
                        if col_name:  # Si la columna tiene nombre
                            row[col_name] = raw_values[i]
                        # Columnas sin nombre las guardamos con nombres especiales
                        elif i == 8:  # Primera columna sin nombre (monto)
                            row['__amount__'] = raw_values[i]
                        elif i == 10:  # Segunda columna sin nombre (saldo)
                            row['__balance__'] = raw_values[i]
                
                self._process_row(row)
        
        # Calcular holdings desde trades
        self._calculate_holdings()
        
        # Consolidar dividendos con su conversión FX y retención
        self._consolidate_dividends()
        
        # Retornar datos normalizados
        return {
            'broker': 'DEGIRO',
            'account_info': self.account_info,
            'trades': self.trades,
            'holdings': list(self.holdings.values()),
            'dividends': self.dividends,
            'deposits': self.deposits,
            'withdrawals': self.withdrawals,
            'fees': self.fees,
            'fx_transactions': self.fx_transactions
        }
    
    def _process_row(self, row: Dict[str, str]):
        """Procesa una fila del CSV"""
        description = row.get('Descripción', '').strip()
        producto = row.get('Producto', '').strip()
        
        # Detectar tipo de transacción
        # IMPORTANTE: El CSV "Estado de Cuenta" NO debe importar compras/ventas
        # porque ya están en el CSV "Transacciones" (más completo y preciso)
        
        # 1. DIVIDENDOS
        if description == 'Dividendo':
            self._store_dividend_for_consolidation(row)
        
        # 2. RETENCIÓN DE DIVIDENDOS
        elif 'Retención del dividendo' in description or description == 'Retención del dividendo':
            self._store_dividend_tax_for_consolidation(row)
        
        # 3. CONVERSIÓN DE DIVISA (para dividendos)
        elif 'Cambio de Divisa' in description:
            # Si NO tiene producto, guardar para emparejar con dividendos
            if not producto:
                if 'Ingreso' in description:
                    self._store_fx_deposit(row)
                elif 'Retirada' in description:
                    self._store_fx_withdrawal(row)
            # Si tiene producto, ignorar (no parece ocurrir en tu CSV)
        
        # 4. INTERÉS (Apalancamiento)
        elif 'Interés' in description or description == 'Interés':
            self._process_interest(row)
        
        # 5. RETIROS (flatex Withdrawal)
        elif 'flatex Withdrawal' in description:
            self._process_withdrawal(row)
        
        # 6. DEPÓSITOS (solo "Ingreso", NO "Ingreso Cambio de Divisa")
        elif description == 'Ingreso':
            self._process_deposit(row)
        
        # 7. COMISIONES GENERALES (conectividad, etc.)
        elif 'Costes de transacción' in description or 'Comisión' in description:
            # IMPORTANTE: Filtrar "Costes de transacción" que hacen referencia a un asset
            # porque ya están incluidos en el CSV de Transacciones
            if 'Costes de transacción' in description and producto:
                # Es una comisión de transacción específica → IGNORAR (duplicado)
                pass
            else:
                # Es una comisión general (conectividad, etc.) → REGISTRAR
                self._process_fee(row)
    
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
    
    def _process_fee(self, row: Dict[str, str]):
        """Procesa comisiones y costes"""
        # Extraer monto de columna sin nombre
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', 'EUR').strip()
        
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
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', 'EUR').strip()
        
        fx = {
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': amount_value,
            'currency': currency,
            'exchange_rate': self._parse_decimal(row.get('Tipo', '0')),
            'description': row.get('Descripción', '').strip()
        }
        
        self.fx_transactions.append(fx)
    
    def _store_dividend_for_consolidation(self, row: Dict[str, str]):
        """Almacena un dividendo para consolidar con su conversión FX"""
        producto = row.get('Producto', '').strip()
        fecha = row.get('Fecha', '').strip()
        
        # Extraer monto en divisa original
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', '').strip()
        
        # Clave única: monto_absoluto + divisa + símbolo (para emparejar con FX)
        # Usamos el monto redondeado para evitar problemas de precisión
        key = f"{abs(amount_value):.2f}_{currency}_{producto}"
        
        if key not in self.dividend_fx_map:
            self.dividend_fx_map[key] = {}
        
        self.dividend_fx_map[key]['dividend'] = {
            'symbol': producto,
            'isin': row.get('ISIN', '').strip(),
            'date': self._parse_date(fecha),
            'amount_original': amount_value,
            'currency_original': currency,
            'amount_eur': Decimal('0'),  # Se llenará con FX
            'tax': Decimal('0')  # Se llenará con retención
        }
    
    def _store_dividend_tax_for_consolidation(self, row: Dict[str, str]):
        """Almacena retención de dividendo para consolidar"""
        producto = row.get('Producto', '').strip()
        
        # Extraer monto de retención
        tax_value = abs(self._extract_first_unnamed_column(row))  # Absoluto
        currency = row.get('Variación', 'EUR').strip()
        
        # Buscar la clave del dividendo correspondiente
        # Intentar emparejar con dividendo existente por símbolo
        for dict_key in self.dividend_fx_map.keys():
            if producto in dict_key:
                if 'dividend' not in self.dividend_fx_map[dict_key]:
                    self.dividend_fx_map[dict_key]['dividend'] = {}
                self.dividend_fx_map[dict_key]['dividend']['tax'] = tax_value
                break
    
    def _store_fx_withdrawal(self, row: Dict[str, str]):
        """Almacena Retirada Cambio de Divisa (conversión FROM divisa extranjera)"""
        # Extraer monto y divisa
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', '').strip()
        
        self.fx_withdrawals.append({
            'amount': abs(amount_value),
            'currency': currency,
            'date': row.get('Fecha', '')
        })
    
    def _store_fx_deposit(self, row: Dict[str, str]):
        """Almacena Ingreso Cambio de Divisa (monto en EUR)"""
        # Extraer monto en EUR
        amount_eur = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', 'EUR').strip()
        
        self.fx_deposits.append({
            'amount': abs(amount_eur),
            'currency': currency,
            'date': row.get('Fecha', '')
        })
    
    def _consolidate_dividends(self):
        """Consolida dividendos con validación numérica estricta"""
        from datetime import datetime, timedelta
        
        self.dividends = []  # Limpiar lista temporal
        processed_dividends = set()  # Para evitar duplicados
        
        for key, data in self.dividend_fx_map.items():
            if key in processed_dividends:
                continue
                
            dividend_data = data.get('dividend', {})
            if not dividend_data:
                continue
            
            symbol = dividend_data.get('symbol', '')
            amount_original = dividend_data.get('amount_original', Decimal('0'))
            currency_original = dividend_data.get('currency_original', 'EUR')
            date_str = dividend_data.get('date', '')
            isin = dividend_data.get('isin', '')
            
            # El tax ya está almacenado en dividend_data por _store_dividend_tax_for_consolidation
            tax_amount = dividend_data.get('tax', Decimal('0'))
            
            try:
                dividend_date = datetime.strptime(date_str, '%Y-%m-%d')
            except:
                continue
            
            # CASO 3: Dividendo en EUR (moneda base)
            if currency_original == 'EUR':
                self.dividends.append({
                    'symbol': symbol,
                    'isin': isin,
                    'date': date_str,
                    'amount': float(amount_original),
                    'currency': 'EUR',
                    'tax': float(tax_amount),
                    'description': 'Dividendo'
                })
                processed_dividends.add(key)
                continue
            
            # CASO 1 y 2: Dividendo en divisa extranjera
            # Calcular monto neto para buscar en FX Withdrawal
            net_amount = amount_original - tax_amount
            
            # Buscar "Retirada Cambio de Divisa" que coincida
            matched_withdrawal = None
            for fx_w in self.fx_withdrawals:
                # Verificar monto y divisa
                if (abs(fx_w['amount'] - abs(net_amount)) < Decimal('0.5') and 
                    fx_w['currency'] == currency_original):
                    # Verificar fecha (dentro de 5 días)
                    try:
                        fx_date = datetime.strptime(fx_w['date'], '%d-%m-%Y')
                        if abs((fx_date - dividend_date).days) <= 5:
                            matched_withdrawal = fx_w
                            break
                    except:
                        pass
            
            # Si encontramos withdrawal, buscar ingreso EUR y validar numéricamente
            if matched_withdrawal:
                # Buscar ingreso EUR cercano
                for fx_d in self.fx_deposits:
                    try:
                        deposit_date = datetime.strptime(fx_d['date'], '%d-%m-%Y')
                        if abs((deposit_date - dividend_date).days) <= 5:
                            # El dividendo se queda en moneda local
                            self.dividends.append({
                                'symbol': symbol,
                                'isin': isin,
                                'date': date_str,
                                'amount': float(amount_original),
                                'currency': currency_original,
                                'tax': float(tax_amount),
                                'description': 'Dividendo'
                            })
                            processed_dividends.add(key)
                            break
                    except:
                        pass
            else:
                # No se encontró conversión FX, usar monto original
                self.dividends.append({
                    'symbol': symbol,
                    'isin': isin,
                    'date': date_str,
                    'amount': float(amount_original),
                    'currency': currency_original,
                    'tax': float(tax_amount),
                    'description': 'Dividendo'
                })
                processed_dividends.add(key)
    
    def _process_interest(self, row: Dict[str, str]):
        """Procesa interés (comisión por apalancamiento)"""
        # Extraer monto
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', 'EUR').strip()
        
        fee = {
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': abs(amount_value),
            'currency': currency,
            'description': 'Apalancamiento DeGiro',
            'related_symbol': ''  # Sin asset específico
        }
        
        self.fees.append(fee)
    
    def _process_withdrawal(self, row: Dict[str, str]):
        """Procesa retiro (flatex Withdrawal)"""
        # Extraer monto
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', 'EUR').strip()
        
        withdrawal = {
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': abs(amount_value),  # Absoluto
            'currency': currency,
            'description': row.get('Descripción', '').strip()
        }
        
        self.withdrawals.append(withdrawal)
    
    def _process_deposit(self, row: Dict[str, str]):
        """Procesa depósito (solo 'Ingreso', NO 'Ingreso Cambio de Divisa')"""
        # Extraer monto
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', 'EUR').strip()
        
        deposit = {
            'date': self._parse_date(row.get('Fecha', '')),
            'amount': abs(amount_value),
            'currency': currency,
            'description': row.get('Descripción', '').strip()
        }
        
        self.deposits.append(deposit)
    
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
    
    def _extract_first_unnamed_column(self, row: Dict[str, str]) -> Decimal:
        """Extrae el valor de la primera columna sin nombre (monto de transacción)"""
        # La columna sin nombre (monto) está en '__amount__'
        amount_str = row.get('__amount__', '0')
        return self._parse_decimal(amount_str)
    
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

