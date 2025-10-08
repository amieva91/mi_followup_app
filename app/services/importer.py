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
from app.services.fifo_calculator import FIFOCalculator


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
        # Crear snapshot de transacciones existentes ANTES de importar
        # Solo verificaremos duplicados contra este snapshot, no contra transacciones recién creadas
        self.existing_transactions_snapshot = set()
        for tx in Transaction.query.filter_by(account_id=self.broker_account_id).all():
            # Crear clave única para cada transacción existente
            tx_key = (
                tx.asset_id,
                tx.transaction_type,
                tx.transaction_date.isoformat() if tx.transaction_date else None,
                float(tx.quantity),
                float(tx.price)
            )
            self.existing_transactions_snapshot.add(tx_key)
        
        # Importar en orden: assets, transactions, dividends, fees, deposits
        self._import_assets(parsed_data)
        self._import_transactions(parsed_data)
        self._import_dividends(parsed_data)  # Incluye dividendos y retenciones fiscales
        self._import_fees(parsed_data)  # Comisiones generales
        self._import_cash_movements(parsed_data)  # Depósitos y retiros
        
        # Recalcular holdings desde transacciones (FIFO robusto)
        self._recalculate_holdings()
        
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
        """Importa transacciones evitando duplicados solo entre archivos diferentes"""
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
            
            # Verificar si ya existe en BD (prevenir duplicados entre archivos)
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
        """Importa dividendos como transacciones, incluyendo retención fiscal (tax)"""
        for div_data in parsed_data.get('dividends', []):
            # Buscar asset
            asset = self._find_asset(div_data.get('symbol'), div_data.get('isin'))
            
            if not asset:
                # Para dividendos sin símbolo claro, podemos crear una transacción genérica
                continue
            
            # Verificar duplicados
            if self._dividend_exists(div_data, asset.id):
                continue
            
            # Crear transacción de dividendo
            # tax se registra en el mismo registro (campo tax de Transaction)
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
                tax=float(div_data.get('tax', 0)),  # Retención fiscal en divisa original
                tax_eur=float(div_data.get('tax_eur', 0)),  # Retención en EUR (solo para divisas extranjeras)
                description=div_data.get('description', 'Dividendo'),
                source=f"CSV_{parsed_data['broker']}"
            )
            
            db.session.add(transaction)
            self.stats['dividends_created'] += 1
    
    def _import_fees(self, parsed_data: Dict[str, Any]):
        """Importa comisiones generales como transacciones tipo FEE"""
        for fee_data in parsed_data.get('fees', []):
            # Las comisiones generales no tienen asset, usar el campo related_symbol si existe
            asset = None
            if fee_data.get('related_symbol'):
                asset = self._find_asset(fee_data.get('related_symbol'), None)
            
            # Crear transacción de comisión
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=asset.id if asset else None,
                transaction_type='FEE',
                transaction_date=self._parse_datetime(fee_data.get('date')),
                quantity=0,
                price=0,
                amount=-abs(float(fee_data['amount'])),  # Negativo porque es un gasto
                currency=fee_data['currency'],
                description=fee_data.get('description', 'Comisión'),
                source=f"CSV_{parsed_data['broker']}"
            )
            
            db.session.add(transaction)
            self.stats.setdefault('fees_created', 0)
            self.stats['fees_created'] += 1
    
    def _import_cash_movements(self, parsed_data: Dict[str, Any]):
        """Importa depósitos y retiros como transacciones"""
        # Depósitos
        for deposit_data in parsed_data.get('deposits', []):
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=None,  # Los depósitos no tienen asset
                transaction_type='DEPOSIT',
                transaction_date=self._parse_datetime(deposit_data.get('date')),
                quantity=0,
                price=0,
                amount=abs(float(deposit_data['amount'])),  # Positivo
                currency=deposit_data.get('currency', 'EUR'),
                description=deposit_data.get('description', 'Depósito'),
                source=f"CSV_{parsed_data['broker']}"
            )
            
            db.session.add(transaction)
            self.stats.setdefault('deposits_created', 0)
            self.stats['deposits_created'] += 1
        
        # Retiros (ahora vienen directamente parseados)
        for withdrawal_data in parsed_data.get('withdrawals', []):
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=None,
                transaction_type='WITHDRAWAL',
                transaction_date=self._parse_datetime(withdrawal_data.get('date')),
                quantity=0,
                price=0,
                amount=abs(float(withdrawal_data['amount'])),  # Positivo (ya se maneja con signo en la UI)
                currency=withdrawal_data.get('currency', 'EUR'),
                description=withdrawal_data.get('description', 'Retiro'),
                source=f"CSV_{parsed_data['broker']}"
            )
            
            db.session.add(transaction)
            self.stats.setdefault('withdrawals_created', 0)
            self.stats['withdrawals_created'] += 1
    
    def _recalculate_holdings(self):
        """Recalcula holdings desde las transacciones usando FIFO robusto"""
        print("🔄 Recalculando holdings con FIFO robusto...")
        
        # Obtener todas las transacciones BUY/SELL de esta cuenta
        transactions = Transaction.query.filter_by(
            account_id=self.broker_account_id,
            user_id=self.user_id
        ).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).order_by(Transaction.transaction_date).all()
        
        print(f"   📝 Procesando {len(transactions)} transacciones...")
        
        # Agrupar por asset y usar FIFOCalculator
        fifo_calculators = {}
        asset_symbols = {}  # Para debugging
        
        for tx in transactions:
            if tx.asset_id not in fifo_calculators:
                symbol = tx.asset.symbol if tx.asset else 'Unknown'
                fifo_calculators[tx.asset_id] = FIFOCalculator(symbol)
                asset_symbols[tx.asset_id] = symbol
            
            calc = fifo_calculators[tx.asset_id]
            
            if tx.transaction_type == 'BUY':
                calc.add_buy(
                    quantity=tx.quantity,
                    price=tx.price,
                    date=tx.transaction_date,
                    total_cost=tx.amount
                )
            elif tx.transaction_type == 'SELL':
                try:
                    calc.add_sell(
                        quantity=tx.quantity,
                        date=tx.transaction_date
                    )
                except Exception as e:
                    print(f"⚠️  Error procesando venta de {asset_symbols.get(tx.asset_id, 'Unknown')}: {e}")
        
        # Eliminar todos los holdings existentes de esta cuenta
        PortfolioHolding.query.filter_by(
            account_id=self.broker_account_id,
            user_id=self.user_id
        ).delete()
        
        # Crear holdings solo para posiciones abiertas
        for asset_id, calc in fifo_calculators.items():
            if calc.is_closed():
                continue  # No crear holding si la posición está cerrada
            
            position = calc.get_current_position()
            
            if position['quantity'] <= 0:
                continue  # Saltar holdings con cantidad 0 o negativa
            
            holding = PortfolioHolding(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=asset_id,
                quantity=position['quantity'],
                total_cost=position['total_cost'],
                average_buy_price=position['average_buy_price'],
                first_purchase_date=position['first_purchase_date'].date() if isinstance(position['first_purchase_date'], datetime) else position['first_purchase_date'],
                last_transaction_date=position['last_transaction_date'].date() if isinstance(position['last_transaction_date'], datetime) else position['last_transaction_date']
            )
            db.session.add(holding)
            self.stats['holdings_created'] += 1
        
        print(f"   ✅ {self.stats['holdings_created']} holdings creados (solo posiciones abiertas)")
    
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
        """
        Verifica si una transacción ya existía ANTES de esta importación.
        Usa un snapshot para evitar detectar como duplicadas las transacciones que acabamos de crear.
        """
        # Crear clave única de la transacción actual
        date = self._parse_datetime(trade_data.get('date_time') or trade_data.get('date'))
        tx_type = trade_data.get('transaction_type')
        
        tx_key = (
            asset_id,
            tx_type,
            date.isoformat() if date else None,
            float(trade_data['quantity']),
            float(trade_data['price'])
        )
        
        # Verificar solo contra el snapshot (transacciones que existían ANTES de esta importación)
        return tx_key in self.existing_transactions_snapshot
    
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

