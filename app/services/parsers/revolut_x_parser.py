"""
Revolut X Parser - Parsea CSV de extracto Revolut X (criptomonedas)
Formato: Symbol,Type,Quantity,Price,Value,Fees,Date
"""
import csv
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional


def _parse_amount(val: str) -> float:
    """Convierte €6.76 o similar a 6.76"""
    if not val or not val.strip():
        return 0.0
    s = str(val).strip().replace(',', '.').replace('€', '').replace('$', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(date_str: str) -> Optional[datetime]:
    """
    Parsea fecha en formato "21 Jun 2019, 20:52:02" o "4 Feb 2026, 06:20:04"
    Soporta meses en inglés y español
    """
    if not date_str or not date_str.strip():
        return None
    s = date_str.strip()
    s = re.sub(r'\s+', ' ', s)
    formats = [
        "%d %b %Y, %H:%M:%S",
        "%d %b %Y, %H:%M",
        "%d %b %Y",
    ]
    months_es = {'Ene': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Abr': 'Apr', 'May': 'May',
                 'Jun': 'Jun', 'Jul': 'Jul', 'Ago': 'Aug', 'Sep': 'Sep', 'Sept': 'Sep',
                 'Oct': 'Oct', 'Nov': 'Nov', 'Dic': 'Dec'}
    for abbr_es, abbr_en in months_es.items():
        s = re.sub(rf'\b{abbr_es}\b', abbr_en, s, flags=re.IGNORECASE)
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _normalize_type(csv_type: str) -> str:
    """Mapea tipo CSV a tipo interno"""
    t = (csv_type or '').strip().lower()
    if t == 'buy':
        return 'BUY'
    if t == 'sell':
        return 'SELL'
    if t == 'receive':
        return 'BUY'
    if 'staking' in t or 'reward' in t:
        return 'STAKING_REWARD'
    return 'BUY'


class RevolutXParser:
    """Parser para extracto Revolut X (criptomonedas)"""

    def __init__(self):
        self.trades: List[Dict[str, Any]] = []
        self.dividends: List[Dict[str, Any]] = []
        self.fees: List[Dict[str, Any]] = []

    def parse(self, file_path: str) -> Dict[str, Any]:
        """Parsea un archivo CSV de Revolut X"""
        self.trades = []
        self.dividends = []
        self.fees = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return self._empty_result()

            for row in reader:
                self._process_row(row)

        holdings = self._calculate_holdings()

        return {
            'broker': 'REVOLUT_X',
            'format': 'REVOLUT_X',
            'account_info': {},
            'trades': self.trades,
            'dividends': self.dividends,
            'holdings': holdings,
            'deposits': [],
            'fees': self.fees,
            'fx_transactions': [],
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            'broker': 'REVOLUT_X',
            'format': 'REVOLUT_X',
            'account_info': {},
            'trades': [],
            'dividends': [],
            'holdings': [],
            'deposits': [],
            'fees': [],
            'fx_transactions': [],
        }

    def _process_row(self, row: Dict[str, str]) -> None:
        symbol = (row.get('Symbol') or '').strip()
        if not symbol:
            return

        csv_type = (row.get('Type') or '').strip()
        tx_type = _normalize_type(csv_type)

        try:
            quantity = float((row.get('Quantity') or '0').replace(',', '.'))
        except ValueError:
            quantity = 0.0

        if quantity <= 0 and tx_type != 'STAKING_REWARD':
            return

        price = _parse_amount(row.get('Price', ''))
        value = _parse_amount(row.get('Value', ''))
        fees = _parse_amount(row.get('Fees', ''))
        date_dt = _parse_date(row.get('Date', ''))

        if not date_dt:
            return

        isin = f"CRYPTO:{symbol}"[:12]

        if tx_type == 'STAKING_REWARD':
            # Staking reward = BUY con coste 0 (añade cantidad al holding)
            # No se añade a dividends para evitar duplicados
            trade = {
                'transaction_type': 'BUY',
                'symbol': symbol,
                'name': f'{symbol} (Crypto)',
                'isin': isin,
                'date': date_dt,
                'date_time': date_dt,
                'quantity': quantity,
                'price': 0.0,
                'amount': 0.0,
                'currency': 'EUR',
                'commission': 0.0,
                'fees': 0.0,
                'order_id': '',
                'description': f'Staking reward {quantity} {symbol}',
                'asset_type': 'Crypto',
                'asset_type_csv': 'Crypto',
                'is_reward': True,
            }
            self.trades.append(trade)
        else:
            amount = value if value else abs(price * quantity)
            if tx_type == 'SELL':
                amount = abs(amount)
            else:
                amount = -abs(amount)

            trade = {
                'transaction_type': tx_type,
                'symbol': symbol,
                'name': f'{symbol} (Crypto)',
                'isin': isin,
                'date': date_dt,
                'date_time': date_dt,
                'quantity': abs(quantity),
                'price': price if price else (abs(value) / quantity if quantity else 0),
                'amount': amount,
                'currency': 'EUR',
                'commission': fees,
                'fees': fees,
                'order_id': '',
                'description': f"{'Compra' if tx_type == 'BUY' else 'Venta'} {abs(quantity)} {symbol}",
                'asset_type': 'Crypto',
                'asset_type_csv': 'Crypto',
                'is_reward': False,
            }
            self.trades.append(trade)

    def _calculate_holdings(self) -> List[Dict[str, Any]]:
        """Calcula posiciones actuales por symbol"""
        pos: Dict[str, Dict[str, Any]] = {}

        for trade in self.trades:
            symbol = trade['symbol']
            isin = trade['isin']

            if symbol not in pos:
                pos[symbol] = {
                    'symbol': symbol,
                    'name': f'{symbol} (Crypto)',
                    'isin': isin,
                    'currency': 'EUR',
                    'quantity': Decimal('0'),
                    'total_cost': Decimal('0'),
                    'average_buy_price': Decimal('0'),
                    'asset_type': 'Crypto',
                }

            h = pos[symbol]
            qty = Decimal(str(trade['quantity']))
            price = Decimal(str(trade['price']))
            cost = qty * price + Decimal(str(trade.get('commission', 0) or 0))

            if trade['transaction_type'] == 'BUY':
                h['quantity'] += qty
                h['total_cost'] += cost
            else:
                h['quantity'] -= qty
                if h['quantity'] > Decimal('0'):
                    cost_per = h['total_cost'] / (h['quantity'] + qty)
                    h['total_cost'] -= cost_per * qty
                else:
                    h['total_cost'] = Decimal('0')

            if h['quantity'] > Decimal('0'):
                h['average_buy_price'] = h['total_cost'] / h['quantity']

        result = []
        for h in pos.values():
            if h['quantity'] > Decimal('0'):
                result.append({
                    'symbol': h['symbol'],
                    'name': h['name'],
                    'isin': h['isin'],
                    'currency': h['currency'],
                    'quantity': float(h['quantity']),
                    'total_cost': float(h['total_cost']),
                    'average_buy_price': float(h['average_buy_price']),
                    'asset_type': h['asset_type'],
                })
        return result
