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
        self.dividend_related_rows = []  # Todas las filas relacionadas con dividendos (para casos complejos como Alibaba)
        
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
        
        # NUEVA LÓGICA UNIFICADA: Almacenar todas las filas relacionadas con dividendos
        # Criterios: tienen ISIN, NO tienen ID Orden (excepto FX que no tienen producto)
        isin = row.get('ISIN', '').strip()
        id_orden = row.get('ID Orden', '').strip()
        
        # 1. FILAS RELACIONADAS CON DIVIDENDOS (tienen ISIN, no tienen ID Orden)
        if isin and not id_orden:
            self._store_dividend_related_row(row)
        
        # 2. CONVERSIÓN DE DIVISA (para dividendos, NO tienen producto ni ISIN)
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
    
    def _store_dividend_related_row(self, row: Dict[str, str]):
        """
        Almacena una fila relacionada con dividendos (nueva lógica unificada)
        Incluye: Dividendo, Retención, Rendimiento de capital, Pass-Through Fee, etc.
        """
        from datetime import datetime
        
        fecha = row.get('Fecha', '').strip()
        hora = row.get('Hora', '').strip()
        isin = row.get('ISIN', '').strip()
        producto = row.get('Producto', '').strip()
        description = row.get('Descripción', '').strip()
        currency = row.get('Variación', '').strip()
        amount_value = self._extract_first_unnamed_column(row)
        
        # Parsear fecha y hora
        try:
            fecha_hora = datetime.strptime(f"{fecha} {hora}", '%d-%m-%Y %H:%M')
        except:
            # Si no tiene hora, usar solo fecha
            try:
                fecha_hora = datetime.strptime(fecha, '%d-%m-%Y')
            except:
                return
        
        self.dividend_related_rows.append({
            'fecha_hora': fecha_hora,
            'isin': isin,
            'producto': producto,
            'description': description,
            'currency': currency,
            'amount': amount_value,  # Puede ser positivo o negativo
            'fecha_str': self._parse_date(fecha)
        })
    
    def _store_dividend_for_consolidation(self, row: Dict[str, str]):
        """Almacena un dividendo para consolidar con su conversión FX"""
        producto = row.get('Producto', '').strip()
        fecha = row.get('Fecha', '').strip()
        
        # Extraer monto en divisa original
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', '').strip()
        
        # Clave única: fecha + monto + divisa + símbolo (para emparejar con FX)
        # Incluimos fecha para evitar colisiones cuando hay múltiples dividendos del mismo monto
        key = f"{fecha}_{abs(amount_value):.2f}_{currency}_{producto}"
        
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
        from datetime import datetime, timedelta
        
        producto = row.get('Producto', '').strip()
        fecha = row.get('Fecha', '').strip()
        
        # Extraer monto de retención
        tax_value = abs(self._extract_first_unnamed_column(row))  # Absoluto
        currency = row.get('Variación', 'EUR').strip()
        
        # Parsear fecha de la retención
        try:
            tax_date = datetime.strptime(fecha, '%d-%m-%Y')
        except:
            return
        
        # Buscar el dividendo correspondiente por fecha, producto y divisa
        # Ahora que la clave incluye fecha, podemos buscar más eficientemente
        best_match = None
        min_date_diff = float('inf')
        
        for dict_key in self.dividend_fx_map.keys():
            # La clave es: fecha_monto_divisa_producto
            # Verificar que sea el mismo producto y divisa
            if producto in dict_key and currency in dict_key:
                dividend_data = self.dividend_fx_map[dict_key].get('dividend', {})
                if not dividend_data:
                    continue
                
                # Comparar fechas (la retención suele estar en la misma fecha que el dividendo)
                try:
                    div_date_str = dividend_data.get('date', '')
                    div_date = datetime.strptime(div_date_str, '%Y-%m-%d')
                    date_diff = abs((tax_date - div_date).days)
                    
                    # Buscar el dividendo más cercano (típicamente mismo día, máx 1 día)
                    if date_diff <= 1 and date_diff < min_date_diff:
                        best_match = dict_key
                        min_date_diff = date_diff
                except:
                    continue
        
        # Asignar la retención al mejor match
        if best_match:
            if 'dividend' not in self.dividend_fx_map[best_match]:
                self.dividend_fx_map[best_match]['dividend'] = {}
            self.dividend_fx_map[best_match]['dividend']['tax'] = tax_value
    
    def _store_fx_withdrawal(self, row: Dict[str, str]):
        """Almacena Retirada Cambio de Divisa (conversión FROM divisa extranjera)"""
        # Extraer monto y divisa
        amount_value = self._extract_first_unnamed_column(row)
        currency = row.get('Variación', '').strip()
        
        # Extraer tipo de cambio (está en la columna "Tipo")
        exchange_rate_str = row.get('Tipo', '0').strip()
        exchange_rate = self._parse_decimal(exchange_rate_str) if exchange_rate_str else Decimal('0')
        
        self.fx_withdrawals.append({
            'amount': abs(amount_value),
            'currency': currency,
            'date': row.get('Fecha', ''),
            'exchange_rate': exchange_rate
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
        """
        NUEVA LÓGICA UNIFICADA: Consolida dividendos agrupando por ISIN + ventana de tiempo
        
        1. Agrupa filas por ISIN + ventana de ±2 horas
        2. Suma positivos - negativos = neto
        3. Busca FX que coincida con ese neto (dentro de 5 días)
        4. Crea UN dividendo consolidado
        """
        from datetime import datetime, timedelta
        
        self.dividends = []
        processed_rows = set()
        
        # Ordenar por fecha/hora
        self.dividend_related_rows.sort(key=lambda x: x['fecha_hora'])
        
        # Agrupar por ISIN + ventana de tiempo
        for i, row in enumerate(self.dividend_related_rows):
            if i in processed_rows:
                continue
            
            # Iniciar un nuevo grupo
            grupo = [row]
            isin = row['isin']
            fecha_hora_ref = row['fecha_hora']
            processed_rows.add(i)
            
            # Buscar filas relacionadas (mismo ISIN, dentro de ±2 horas)
            for j in range(i + 1, len(self.dividend_related_rows)):
                if j in processed_rows:
                    continue
                
                other_row = self.dividend_related_rows[j]
                
                # Verificar mismo ISIN
                if other_row['isin'] != isin:
                    continue
                
                # Verificar ventana de tiempo (±12 horas para capturar reversals del mismo día)
                time_diff = abs((other_row['fecha_hora'] - fecha_hora_ref).total_seconds() / 3600)
                if time_diff <= 12:
                    grupo.append(other_row)
                    processed_rows.add(j)
            
            # Verificar que el grupo tenga al menos UNA fila con "Dividendo"
            has_dividend = any(row['description'] == 'Dividendo' for row in grupo)
            if not has_dividend:
                # Este grupo son solo comisiones/fees sin dividendo real
                continue
            
            # Consolidar el grupo
            self._consolidate_dividend_group(grupo)
    
    def _consolidate_dividend_group(self, grupo):
        """Consolida un grupo de filas relacionadas en un solo dividendo"""
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        if not grupo:
            return
        
        # Extraer información común
        isin = grupo[0]['isin']
        producto = grupo[0]['producto']
        currency = grupo[0]['currency']
        fecha_str = grupo[0]['fecha_str']
        fecha_hora_ref = grupo[0]['fecha_hora']
        
        # Sumar todos los montos (positivos y negativos)
        total_gross = Decimal('0')
        total_negative = Decimal('0')
        
        for row in grupo:
            amount = row['amount']
            if amount > 0:
                total_gross += amount
            else:
                total_negative += abs(amount)
        
        # Neto = bruto - retenciones/comisiones
        net_amount = total_gross - total_negative
        
        # Si el neto es 0 (o casi 0), no crear dividendo (reversals/correcciones)
        if abs(net_amount) < Decimal('0.01'):
            return
        
        # CASO 1: Dividendo en EUR (moneda base)
        if currency == 'EUR':
            # Mostrar el NETO (igual que los casos con conversión FX)
            self.dividends.append({
                'symbol': producto,
                'isin': isin,
                'date': fecha_str,
                'amount': float(net_amount),  # Neto (bruto - retención)
                'currency': 'EUR',
                'tax': 0.0,  # No mostramos retenciones
                'tax_eur': 0.0,
                'description': 'Dividendo'
            })
            return
        
        # CASO 2: Dividendo en divisa extranjera → Calcular con tasa de cambio
        # Buscar "Retirada Cambio de Divisa" solo por moneda + fecha (SIN validar monto)
        # Esto funciona para casos individuales Y agrupados
        matched_withdrawal = None
        for fx_w in self.fx_withdrawals:
            # Solo verificar moneda (no monto, para soportar FX agrupadas)
            if fx_w['currency'] == currency:
                # Verificar fecha (dentro de 5 días)
                try:
                    fx_date = datetime.strptime(fx_w['date'], '%d-%m-%Y')
                    dividend_date = datetime.strptime(fecha_str, '%Y-%m-%d')
                    if abs((fx_date - dividend_date).days) <= 5:
                        # Verificar que tenga tasa de cambio válida
                        if fx_w.get('exchange_rate', Decimal('0')) > 0:
                            matched_withdrawal = fx_w
                            break
                except:
                    pass
        
        if not matched_withdrawal:
            # No se encontró conversión FX, usar monto original
            self.dividends.append({
                'symbol': producto,
                'isin': isin,
                'date': fecha_str,
                'amount': float(net_amount),
                'currency': currency,
                'tax': 0.0,
                'tax_eur': 0.0,
                'description': 'Dividendo'
            })
            return
        
        # Calcular directamente con tasa de cambio
        # Esto funciona para casos individuales Y agrupados
        exchange_rate = matched_withdrawal.get('exchange_rate', Decimal('0'))
        eur_amount = net_amount / exchange_rate
        
        self.dividends.append({
            'symbol': producto,
            'isin': isin,
            'date': fecha_str,
            'amount': float(eur_amount),  # Calculado directamente
            'currency': 'EUR',
            'amount_original': float(total_gross),  # Bruto original
            'currency_original': currency,
            'tax': 0.0,  # No mostramos retenciones en casos complejos
            'tax_eur': 0.0,
            'description': 'Dividendo'
        })
    
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

