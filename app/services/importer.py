"""
Importer Service - Importa datos parseados de CSV a la base de datos
"""
from typing import Dict, List, Any
from datetime import datetime
from decimal import Decimal
from app import db
from app.models import (
    User, BrokerAccount, Broker, Asset, 
    PortfolioHolding, Transaction, CashFlow
)


class CSVImporter:
    """Importa datos parseados de CSV a la base de datos"""
    
    def __init__(self, user_id: int, broker_account_id: int):
        """
        Args:
            user_id: ID del usuario
            broker_account_id: ID de la cuenta de broker
        """
        self.user_id = user_id
        self.broker_account_id = broker_account_id
        self.broker_account = BrokerAccount.query.get(broker_account_id)
        
        if not self.broker_account:
            raise ValueError(f"BrokerAccount {broker_account_id} no encontrado")
        
        if self.broker_account.user_id != user_id:
            raise ValueError("La cuenta no pertenece al usuario")
        
        self.stats = {
            'assets_created': 0,
            'assets_updated': 0,
            'transactions_created': 0,
            'transactions_skipped': 0,
            'holdings_created': 0,
            'holdings_updated': 0,
            'dividends_created': 0
        }
    
    def import_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Importa todos los datos parseados
        
        Args:
            parsed_data: Diccionario con datos parseados (salida del parser)
            
        Returns:
            Dict con estadísticas de importación
        """
        # Importar en orden: assets, transactions, dividends
        self._import_assets(parsed_data)
        self._import_transactions(parsed_data)
        self._import_dividends(parsed_data)
        
        # Recalcular holdings desde transacciones
        self._recalculate_holdings()
        
        # Limpieza final: eliminar holdings con quantity <= 0 o negativa
        self._cleanup_zero_holdings()
        
        db.session.commit()
        
        return self.stats
    
    def _import_assets(self, parsed_data: Dict[str, Any]):
        """Crea o actualiza assets desde los datos parseados"""
        # Recopilar todos los símbolos únicos de trades y holdings
        symbols = set()
        
        for trade in parsed_data.get('trades', []):
            if trade.get('symbol'):
                symbols.add((
                    trade['symbol'],
                    trade.get('isin', ''),
                    trade.get('currency', 'USD')
                ))
        
        for holding in parsed_data.get('holdings', []):
            if holding.get('symbol'):
                symbols.add((
                    holding['symbol'],
                    holding.get('isin', ''),
                    holding.get('currency', 'USD')
                ))
        
        # Crear o actualizar assets
        for symbol, isin, currency in symbols:
            asset = self._get_or_create_asset(
                symbol=symbol,
                isin=isin,
                currency=currency,
                asset_type=parsed_data.get('asset_type', 'Stock')
            )
    
    def _get_or_create_asset(self, symbol: str, isin: str, currency: str, asset_type: str = 'Stock') -> Asset:
        """Obtiene o crea un asset (catálogo global)"""
        # Buscar por ISIN (si existe) - tiene prioridad porque es único
        if isin:
            asset = Asset.query.filter_by(isin=isin).first()
            if asset:
                # Actualizar símbolo si es diferente
                if asset.symbol != symbol:
                    asset.symbol = symbol
                    self.stats['assets_updated'] += 1
                return asset
        
        # Buscar por símbolo + divisa
        asset = Asset.query.filter_by(symbol=symbol, currency=currency).first()
        
        if asset:
            # Actualizar ISIN si no lo tiene
            if isin and not asset.isin:
                asset.isin = isin
                self.stats['assets_updated'] += 1
            return asset
        
        # Crear nuevo asset
        asset = Asset(
            symbol=symbol,
            isin=isin or None,
            name=symbol,  # Usar símbolo como nombre por defecto
            asset_type=asset_type,
            currency=currency
        )
        db.session.add(asset)
        db.session.flush()  # Para obtener el ID
        
        self.stats['assets_created'] += 1
        return asset
    
    def _import_transactions(self, parsed_data: Dict[str, Any]):
        """Importa transacciones evitando duplicados"""
        for trade_data in parsed_data.get('trades', []):
            # Filtrar transacciones FX (cambio de divisa) - no son posiciones reales
            asset_type = trade_data.get('asset_type', '').lower()
            if 'fórex' in asset_type or 'forex' in asset_type or 'fx' in asset_type:
                continue
            
            # Buscar asset
            asset = self._find_asset(trade_data.get('symbol'), trade_data.get('isin'))
            
            if not asset:
                print(f"⚠️  Asset no encontrado: {trade_data.get('symbol')}")
                continue
            
            # Verificar si ya existe (por external_id o fecha+cantidad+precio)
            if self._transaction_exists(trade_data, asset.id):
                self.stats['transactions_skipped'] += 1
                continue
            
            # Calcular el monto correcto (siempre positivo para BUY, calculado desde cantidad*precio)
            quantity = float(trade_data['quantity'])
            price = float(trade_data['price'])
            amount = abs(quantity * price)  # Usar valor absoluto
            commission = abs(float(trade_data.get('commission', 0)))  # Comisión siempre positiva
            
            # Crear transacción
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=asset.id,
                transaction_type=trade_data['transaction_type'],
                transaction_date=self._parse_datetime(trade_data.get('date_time') or trade_data.get('date')),
                quantity=quantity,
                price=price,
                amount=amount,
                currency=trade_data['currency'],
                commission=commission,
                external_id=trade_data.get('order_id'),
                description=trade_data.get('description'),
                source=f"CSV_{parsed_data['broker']}"
            )
            
            # Calcular P&L realizada si es venta
            if trade_data['transaction_type'] == 'SELL':
                transaction.realized_pl = float(trade_data.get('realized_pl', 0))
            
            db.session.add(transaction)
            self.stats['transactions_created'] += 1
    
    def _import_dividends(self, parsed_data: Dict[str, Any]):
        """Importa dividendos como transacciones tipo DIVIDEND"""
        for div_data in parsed_data.get('dividends', []):
            # Ignorar retenciones de impuestos (las registraremos en la transacción principal)
            if div_data.get('is_tax'):
                continue
            
            # Buscar asset
            asset = self._find_asset(div_data.get('symbol'), div_data.get('isin'))
            
            if not asset:
                # Para dividendos sin símbolo claro, podemos crear una transacción genérica
                continue
            
            # Verificar duplicados
            if self._dividend_exists(div_data, asset.id):
                continue
            
            # Crear transacción de dividendo
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=asset.id,
                transaction_type='DIVIDEND',
                transaction_date=self._parse_datetime(div_data.get('date')),
                quantity=0,  # Los dividendos no tienen cantidad
                price=0,
                amount=float(div_data['amount']),
                currency=div_data['currency'],
                description=div_data.get('description', 'Dividendo'),
                source=f"CSV_{parsed_data['broker']}"
            )
            
            db.session.add(transaction)
            self.stats['dividends_created'] += 1
    
    def _recalculate_holdings(self):
        """Recalcula holdings desde las transacciones de la cuenta"""
        # Obtener todas las transacciones BUY/SELL de esta cuenta
        transactions = Transaction.query.filter_by(
            account_id=self.broker_account_id,
            user_id=self.user_id
        ).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).order_by(Transaction.transaction_date).all()
        
        # Agrupar por asset
        holdings_dict = {}
        
        for tx in transactions:
            if tx.asset_id not in holdings_dict:
                holdings_dict[tx.asset_id] = {
                    'quantity': 0,
                    'total_cost': 0,
                    'first_date': tx.transaction_date,
                    'last_date': tx.transaction_date
                }
            
            h = holdings_dict[tx.asset_id]
            
            if tx.transaction_type == 'BUY':
                h['quantity'] += tx.quantity
                h['total_cost'] += tx.amount
            elif tx.transaction_type == 'SELL':
                # Reducir cantidad y coste proporcionalmente (FIFO simplificado)
                if h['quantity'] > 0:
                    cost_per_share = h['total_cost'] / h['quantity']
                    h['quantity'] -= tx.quantity
                    h['total_cost'] -= cost_per_share * tx.quantity
            
            h['last_date'] = tx.transaction_date
        
        # Crear o actualizar holdings
        for asset_id, data in holdings_dict.items():
            if data['quantity'] <= 0:
                # Eliminar holding si la cantidad es 0
                PortfolioHolding.query.filter_by(
                    account_id=self.broker_account_id,
                    asset_id=asset_id,
                    user_id=self.user_id
                ).delete()
                continue
            
            holding = PortfolioHolding.query.filter_by(
                account_id=self.broker_account_id,
                asset_id=asset_id,
                user_id=self.user_id
            ).first()
            
            asset = Asset.query.get(asset_id)
            
            if holding:
                # Actualizar
                holding.quantity = data['quantity']
                holding.total_cost = data['total_cost']
                holding.average_buy_price = data['total_cost'] / data['quantity']
                holding.last_transaction_date = data['last_date'].date() if isinstance(data['last_date'], datetime) else data['last_date']
                self.stats['holdings_updated'] += 1
            else:
                # Crear
                holding = PortfolioHolding(
                    user_id=self.user_id,
                    account_id=self.broker_account_id,
                    asset_id=asset_id,
                    quantity=data['quantity'],
                    total_cost=data['total_cost'],
                    average_buy_price=data['total_cost'] / data['quantity'],
                    first_purchase_date=data['first_date'].date() if isinstance(data['first_date'], datetime) else data['first_date'],
                    last_transaction_date=data['last_date'].date() if isinstance(data['last_date'], datetime) else data['last_date']
                )
                db.session.add(holding)
                self.stats['holdings_created'] += 1
    
    def _cleanup_zero_holdings(self):
        """Elimina todos los holdings con quantity <= 0 de esta cuenta"""
        deleted_count = PortfolioHolding.query.filter_by(
            account_id=self.broker_account_id
        ).filter(
            PortfolioHolding.quantity <= 0
        ).delete()
        
        if deleted_count > 0:
            print(f"🧹 Limpieza: {deleted_count} holdings con quantity <= 0 eliminados")
    
    # Helper methods
    
    def _find_asset(self, symbol: str, isin: str = None) -> Asset:
        """Encuentra un asset por símbolo o ISIN (catálogo global)"""
        if isin:
            return Asset.query.filter_by(isin=isin).first()
        if symbol:
            return Asset.query.filter_by(symbol=symbol).first()
        return None
    
    def _transaction_exists(self, trade_data: Dict, asset_id: int) -> bool:
        """Verifica si una transacción ya existe"""
        # Por external_id
        if trade_data.get('order_id'):
            exists = Transaction.query.filter_by(
                account_id=self.broker_account_id,
                external_id=trade_data['order_id']
            ).first()
            if exists:
                return True
        
        # Por fecha + cantidad + precio
        date = self._parse_datetime(trade_data.get('date_time') or trade_data.get('date'))
        exists = Transaction.query.filter_by(
            account_id=self.broker_account_id,
            asset_id=asset_id,
            transaction_date=date,
            quantity=float(trade_data['quantity']),
            price=float(trade_data['price'])
        ).first()
        
        return exists is not None
    
    def _dividend_exists(self, div_data: Dict, asset_id: int) -> bool:
        """Verifica si un dividendo ya existe"""
        date = self._parse_datetime(div_data.get('date'))
        exists = Transaction.query.filter_by(
            account_id=self.broker_account_id,
            asset_id=asset_id,
            transaction_type='DIVIDEND',
            transaction_date=date,
            amount=float(div_data['amount'])
        ).first()
        
        return exists is not None
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """Parsea string de fecha/hora a datetime"""
        if not date_str:
            return datetime.now()
        
        if isinstance(date_str, datetime):
            return date_str
        
        # Intentar varios formatos
        formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%d-%m-%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        # Si no se puede parsear, usar fecha actual
        return datetime.now()

