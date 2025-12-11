"""
CSV Importer V2 - Usa AssetRegistry como cache global
"""
from typing import Dict, List, Any, Callable, Union
from datetime import datetime
from decimal import Decimal
from app import db
from app.models import (
    User, BrokerAccount, Asset, AssetRegistry,
    PortfolioHolding, Transaction, CashFlow
)
from app.services.fifo_calculator import FIFOCalculator
from app.services.asset_registry_service import AssetRegistryService


def parse_datetime(date_value: Union[str, datetime, None]) -> Union[datetime, None]:
    """
    Convierte una fecha (string, datetime, o date) a objeto datetime.
    
    Args:
        date_value: Fecha como string ISO, objeto datetime, objeto date, o None
    
    Returns:
        Objeto datetime o None
    """
    from datetime import date
    
    if date_value is None:
        return None
    
    # Si ya es datetime, retornar tal cual
    if isinstance(date_value, datetime):
        return date_value
    
    # Si es date (sin hora), convertir a datetime con hora 00:00:00
    if isinstance(date_value, date):
        return datetime.combine(date_value, datetime.min.time())
    
    if isinstance(date_value, str):
        # Intentar parsear ISO format (YYYY-MM-DDTHH:MM:SS o YYYY-MM-DD)
        try:
            return datetime.fromisoformat(date_value)
        except ValueError:
            # Si falla, intentar solo fecha (YYYY-MM-DD)
            try:
                return datetime.strptime(date_value, '%Y-%m-%d')
            except ValueError:
                # Si todo falla, retornar None
                print(f"⚠️ WARNING: No se pudo parsear fecha: {date_value}")
                return None
    
    return None


class CSVImporterV2:
    """
    Importer V2 - Usa AssetRegistry como cache global compartida
    """
    
    def __init__(self, user_id: int, broker_account_id: int, enable_enrichment: bool = False):
        self.user_id = user_id
        self.broker_account_id = broker_account_id
        self.broker_account = BrokerAccount.query.get(broker_account_id)
        self.registry_service = AssetRegistryService()
        self.enable_enrichment = enable_enrichment  # ⚡ Deshabilitar por defecto para evitar rate limits
        print(f"🔍 DEBUG CSVImporterV2: enable_enrichment = {self.enable_enrichment}")
        
        if not self.broker_account:
            raise ValueError(f"BrokerAccount {broker_account_id} no encontrado")
        
        if self.broker_account.user_id != user_id:
            raise ValueError("La cuenta no pertenece al usuario")
        
        self.stats = {
            'assets_created': 0,
            'registry_created': 0,
            'registry_reused': 0,
            'enrichment_needed': 0,
            'enrichment_success': 0,
            'enrichment_failed': 0,
            'transactions_created': 0,
            'dividends_created': 0,
            'fees_created': 0,
            'deposits_created': 0,
            'withdrawals_created': 0,
        }
        
        # Snapshot de transacciones existentes (para evitar duplicados)
        self.existing_transactions_snapshot = set()
        
        # Cache local de assets creados en esta importación
        self.asset_cache = {}  # {isin: Asset}
    
    def import_data(
        self, 
        parsed_data: Dict[str, Any],
        progress_callback: Callable[[int, int, str], None] = None
    ) -> Dict[str, Any]:
        """
        Importa datos con AssetRegistry y progreso en tiempo real
        
        Args:
            parsed_data: Datos parseados del CSV
            progress_callback: Función para reportar progreso(current, total, message)
        """
        # 1. Crear snapshot de transacciones existentes
        self._create_transaction_snapshot()
        
        # 2. Procesar assets y detectar los que necesitan enriquecimiento
        isins_needed = self._process_assets_to_registry(parsed_data)
        
        # 3. Enriquecer assets que lo necesiten (con progreso) - SOLO si está habilitado
        print(f"🔍 DEBUG: isins_needed = {len(isins_needed) if isins_needed else 0}, enable_enrichment = {self.enable_enrichment}")
        if isins_needed and self.enable_enrichment:
            self.stats['enrichment_needed'] = len(isins_needed)
            print(f"✅ Iniciando enriquecimiento de {len(isins_needed)} assets...")
            self._enrich_assets_with_progress(isins_needed, progress_callback)
        elif isins_needed:
            # Si no está habilitado, solo marcar cuántos quedan pendientes
            self.stats['enrichment_needed'] = len(isins_needed)
            self.stats['enrichment_success'] = 0
            self.stats['enrichment_failed'] = 0
            print(f"⚡ {len(isins_needed)} assets sin enriquecer (enrichment deshabilitado durante import)")
        
        # 4. Crear Assets locales desde AssetRegistry
        self._create_local_assets_from_registry(parsed_data)
        
        # 5. Importar transacciones, dividendos, fees, etc.
        self._import_transactions(parsed_data)
        self._import_dividends(parsed_data)
        self._import_fees(parsed_data)
        self._import_cash_movements(parsed_data)
        
        # 6. Recalcular holdings con FIFO
        self._recalculate_holdings()
        
        # 7. Limpiar holdings cerrados
        self._cleanup_zero_holdings()
        
        # Debug: Contar transacciones pendientes ANTES del commit
        pending_count = len([obj for obj in db.session.new if isinstance(obj, Transaction)])
        print(f"   🔍 DEBUG: {pending_count} transacciones pendientes de commit")
        
        db.session.commit()
        print(f"   ✅ DEBUG: Commit ejecutado correctamente")
        
        # Debug: Verificar transacciones después del commit
        saved_count = Transaction.query.filter_by(user_id=self.user_id, account_id=self.broker_account_id).count()
        print(f"   ✅ DEBUG: {saved_count} transacciones total en esta cuenta después del commit")
        
        return self.stats
    
    def _create_transaction_snapshot(self):
        """Crea snapshot de transacciones existentes"""
        existing = Transaction.query.filter_by(
            user_id=self.user_id,
            account_id=self.broker_account_id
        ).all()
        
        for txn in existing:
            key = (
                txn.transaction_type,
                txn.asset_id,
                txn.transaction_date.isoformat() if txn.transaction_date else None,
                float(txn.quantity) if txn.quantity else 0,
                float(txn.price) if txn.price else 0
            )
            self.existing_transactions_snapshot.add(key)
    
    def _process_assets_to_registry(self, parsed_data: Dict[str, Any]) -> List[str]:
        """
        Procesa todos los assets del CSV y los registra en AssetRegistry
        Retorna lista de ISINs que necesitan enriquecimiento
        """
        isins_in_csv = set()
        assets_dict = {}
        
        # Recopilar assets únicos del CSV
        for trade in parsed_data.get('trades', []):
            if trade.get('isin'):
                isin = trade['isin']
                isins_in_csv.add(isin)
                
                if isin not in assets_dict:
                    assets_dict[isin] = {
                        'isin': isin,
                        'symbol': trade.get('symbol', ''),  # IBKR trae symbol
                        'currency': trade.get('currency', 'USD'),
                        'name': trade.get('name', ''),
                        'exchange': trade.get('exchange', ''),  # IBKR trae exchange unificado
                        'mic': trade.get('mic', ''),
                        'degiro_exchange': trade.get('degiro_exchange', ''),
                        'asset_type': trade.get('asset_type', 'Stock')
                    }
        
        for holding in parsed_data.get('holdings', []):
            if holding.get('isin'):
                isin = holding['isin']
                isins_in_csv.add(isin)
                
                if isin not in assets_dict:
                    assets_dict[isin] = {
                        'isin': isin,
                        'symbol': holding.get('symbol', ''),
                        'currency': holding.get('currency', 'USD'),
                        'name': holding.get('name', ''),
                        'exchange': holding.get('exchange', ''),
                        'mic': holding.get('mic', ''),
                        'degiro_exchange': holding.get('degiro_exchange', ''),
                        'asset_type': holding.get('asset_type', 'Stock')
                    }
        
        for dividend in parsed_data.get('dividends', []):
            if dividend.get('isin'):
                isin = dividend['isin']
                isins_in_csv.add(isin)
                
                if isin not in assets_dict:
                    assets_dict[isin] = {
                        'isin': isin,
                        'symbol': dividend.get('symbol', ''),
                        'currency': dividend.get('currency_original', dividend.get('currency', 'USD')),
                        'name': dividend.get('name', ''),
                        'exchange': dividend.get('exchange', ''),
                        'mic': dividend.get('mic', ''),
                        'degiro_exchange': dividend.get('degiro_exchange', ''),
                        'asset_type': dividend.get('asset_type', 'Stock')
                    }
        
        # Registrar en AssetRegistry
        for asset_data in assets_dict.values():
            registry = self.registry_service.get_or_create_from_isin(**asset_data)
            
            if hasattr(registry, 'id') and registry.id:
                # Ya existía
                self.stats['registry_reused'] += 1
            else:
                # Recién creado
                self.stats['registry_created'] += 1
        
        db.session.commit()
        
        # Identificar cuáles necesitan enriquecimiento
        isins_needing_enrichment = [
            isin for isin in isins_in_csv
            if self._registry_needs_enrichment(isin)
        ]
        
        return isins_needing_enrichment
    
    def _registry_needs_enrichment(self, isin: str) -> bool:
        """
        Verifica si un registro necesita enriquecimiento
        
        Aplica a TODOS los assets (IBKR y DeGiro por igual):
        - Sin symbol → Consultar OpenFIGI para obtener symbol
        - Sin MIC → Consultar OpenFIGI para obtener MIC
        
        No distingue origen del asset (broker), solo verifica campos faltantes
        """
        registry = AssetRegistry.query.filter_by(isin=isin).first()
        if not registry:
            return False
        
        # Falta symbol (puede ser DeGiro o IBKR sin symbol)
        if not registry.symbol:
            return True
        
        # Falta MIC (puede ser IBKR o DeGiro sin MIC)
        if not registry.mic:
            return True
        
        return False
    
    def _enrich_assets_with_progress(
        self,
        isins: List[str],
        progress_callback: Callable[[int, int, str], None] = None
    ):
        """
        Enriquece assets con OpenFIGI, reportando progreso
        Obtiene:
        - Symbol para assets sin symbol (DeGiro)
        - MIC para assets sin MIC (IBKR)
        """
        total = len(isins)
        
        for idx, isin in enumerate(isins, 1):
            registry = AssetRegistry.query.filter_by(isin=isin).first()
            if not registry:
                continue
            
            # Determinar qué falta
            missing = []
            if not registry.symbol:
                missing.append('Symbol')
            if not registry.mic:
                missing.append('MIC')
            
            missing_str = ' + '.join(missing) if missing else 'datos'
            
            # Reportar progreso
            if progress_callback:
                progress_callback(
                    idx, 
                    total, 
                    f"🔍 {registry.name or isin[:12]}: obteniendo {missing_str}..."
                )
            
            # Enriquecer con OpenFIGI
            success, message = self.registry_service.enrich_from_openfigi(registry, update_db=False)
            
            if success:
                self.stats['enrichment_success'] += 1
            else:
                self.stats['enrichment_failed'] += 1
        
        db.session.commit()
    
    def _create_local_assets_from_registry(self, parsed_data: Dict[str, Any]):
        """
        Crea Assets locales del usuario desde AssetRegistry
        """
        isins_needed = set()
        
        # Recopilar ISINs únicos
        for trade in parsed_data.get('trades', []):
            if trade.get('isin'):
                isins_needed.add(trade['isin'])
        
        for holding in parsed_data.get('holdings', []):
            if holding.get('isin'):
                isins_needed.add(holding['isin'])
        
        for dividend in parsed_data.get('dividends', []):
            if dividend.get('isin'):
                isins_needed.add(dividend['isin'])
        
        # Crear Assets locales
        for isin in isins_needed:
            # Verificar si ya existe
            existing = Asset.query.filter_by(isin=isin).first()
            if existing:
                # Si existe, actualizar desde AssetRegistry enriquecido
                registry = AssetRegistry.query.filter_by(isin=isin).first()
                if registry:
                    # Actualizar campos desde registry si están disponibles
                    if registry.symbol and not existing.symbol:
                        existing.symbol = registry.symbol
                    if registry.yahoo_suffix and not existing.yahoo_suffix:
                        existing.yahoo_suffix = registry.yahoo_suffix
                    if registry.mic and not existing.mic:
                        existing.mic = registry.mic
                    if registry.name and existing.name != registry.name:
                        existing.name = registry.name
                    if registry.ibkr_exchange and not existing.exchange:
                        existing.exchange = registry.ibkr_exchange
                self.asset_cache[isin] = existing
                continue
            
            # Obtener desde registro
            registry = AssetRegistry.query.filter_by(isin=isin).first()
            if not registry:
                continue
            
            # Crear Asset local
            asset = self.registry_service.create_asset_from_registry(registry, self.user_id)
            self.asset_cache[isin] = asset
            self.stats['assets_created'] += 1
        
        db.session.commit()
    
    def _find_asset_by_isin(self, isin: str) -> Asset:
        """Busca asset por ISIN (usa cache local primero)"""
        if isin in self.asset_cache:
            return self.asset_cache[isin]
        
        asset = Asset.query.filter_by(isin=isin).first()
        if asset:
            self.asset_cache[isin] = asset
        
        return asset
    
    # Métodos de importación (copiados del importer original)
    def _import_transactions(self, parsed_data: Dict[str, Any]):
        """Importa transacciones (BUY/SELL)"""
        trades_list = parsed_data.get('trades', [])
        print(f"   🔍 DEBUG _import_transactions: {len(trades_list)} trades en parsed_data")
        
        skipped_forex = 0
        skipped_no_asset = 0
        skipped_duplicate = 0
        created = 0
        
        for trade_data in trades_list:
            # Filtrar Forex
            asset_type_csv = trade_data.get('asset_type_csv', '')
            if asset_type_csv and ('fórex' in asset_type_csv.lower() or 'forex' in asset_type_csv.lower()):
                skipped_forex += 1
                continue
            
            asset = self._find_asset_by_isin(trade_data.get('isin'))
            if not asset:
                skipped_no_asset += 1
                continue
            
            # Verificar duplicados
            # Usar date_time si está disponible (IBKR), sino date (DeGiro)
            trade_date_raw = trade_data.get('date_time') or trade_data.get('date')
            trade_date = parse_datetime(trade_date_raw)
            trade_date_str = trade_date.isoformat() if trade_date else ''
            
            txn_key = (
                trade_data['transaction_type'],
                asset.id,
                trade_date_str,
                float(trade_data.get('quantity', 0)),
                float(trade_data.get('price', 0))
            )
            
            if txn_key in self.existing_transactions_snapshot:
                skipped_duplicate += 1
                continue
            
            # Crear transacción
            amount = abs(trade_data['price'] * trade_data['quantity'])
            if trade_data['transaction_type'] == 'BUY':
                amount = -amount
            
            # Determinar fechas (IBKR tiene date_time, DeGiro tiene date)
            # Convertir strings a datetime objects
            txn_date_raw = trade_data.get('date_time') or trade_data.get('date')
            settlement_raw = trade_data.get('date') or trade_data.get('date_time')
            
            txn_date = parse_datetime(txn_date_raw)
            settlement = parse_datetime(settlement_raw)
            
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=asset.id,
                transaction_type=trade_data['transaction_type'],
                transaction_date=txn_date,
                settlement_date=settlement,
                quantity=float(trade_data['quantity']),
                price=float(trade_data['price']),
                amount=float(amount),
                currency=trade_data['currency'],
                commission=float(trade_data.get('commission', 0)),
                fees=float(trade_data.get('fees', 0)),
                tax=float(trade_data.get('tax', 0)),
                external_id=trade_data.get('order_id'),
                description=trade_data.get('description', ''),
                source=parsed_data.get('broker', 'CSV')
            )
            
            db.session.add(transaction)
            self.stats['transactions_created'] += 1
            created += 1
        
        # Debug: Reporte final
        print(f"   📊 DEBUG _import_transactions: Forex={skipped_forex}, NoAsset={skipped_no_asset}, Duplicados={skipped_duplicate}, Creadas={created}")
    
    def _import_dividends(self, parsed_data: Dict[str, Any]):
        """Importa dividendos"""
        for div_data in parsed_data.get('dividends', []):
            asset = self._find_asset_by_isin(div_data.get('isin'))
            if not asset:
                continue
            
            # Determinar fecha (con fallback) y convertir a datetime
            div_date_raw = div_data.get('date') or div_data.get('date_time')
            div_date = parse_datetime(div_date_raw)
            
            # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
            if not div_date:
                print(f"   ⚠️  ADVERTENCIA: Dividendo sin fecha para {div_data.get('isin')} - {div_data.get('name')} - Saltado")
                continue
            
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=asset.id,
                transaction_type='DIVIDEND',
                transaction_date=div_date,
                settlement_date=div_date,
                quantity=None,
                price=None,
                amount=float(div_data['amount']),
                currency=div_data.get('currency', 'EUR'),
                tax=float(div_data.get('tax', 0)),
                tax_eur=float(div_data.get('tax_eur', 0)),
                amount_original=float(div_data.get('amount_original')) if div_data.get('amount_original') else None,
                currency_original=div_data.get('currency_original'),
                description=div_data.get('description', 'Dividendo'),
                source=parsed_data.get('broker', 'CSV')
            )
            
            db.session.add(transaction)
            self.stats['dividends_created'] += 1
    
    def _import_fees(self, parsed_data: Dict[str, Any]):
        """Importa comisiones/fees"""
        for fee_data in parsed_data.get('fees', []):
            # Determinar fecha (con fallback) y convertir a datetime
            fee_date_raw = fee_data.get('date') or fee_data.get('date_time')
            fee_date = parse_datetime(fee_date_raw)
            
            # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
            if not fee_date:
                print(f"   ⚠️  ADVERTENCIA: Fee sin fecha ({fee_data.get('description', 'sin descripción')}) - Saltado")
                continue
            
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=None,
                transaction_type='FEE',
                transaction_date=fee_date,
                settlement_date=fee_date,
                quantity=None,
                price=None,
                amount=float(fee_data['amount']),
                currency=fee_data.get('currency', 'EUR'),
                description=fee_data.get('description', 'Comisión'),
                source=parsed_data.get('broker', 'CSV')
            )
            
            db.session.add(transaction)
            self.stats['fees_created'] += 1
    
    def _import_cash_movements(self, parsed_data: Dict[str, Any]):
        """Importa depósitos y retiros"""
        for deposit_data in parsed_data.get('deposits', []):
            # Determinar fecha (con fallback) y convertir a datetime
            deposit_date_raw = deposit_data.get('date') or deposit_data.get('date_time')
            deposit_date = parse_datetime(deposit_date_raw)
            
            # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
            if not deposit_date:
                print(f"   ⚠️  ADVERTENCIA: Depósito sin fecha - Saltado")
                continue
            
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=None,
                transaction_type='DEPOSIT',
                transaction_date=deposit_date,
                settlement_date=deposit_date,
                quantity=None,
                price=None,
                amount=float(deposit_data['amount']),
                currency=deposit_data.get('currency', 'EUR'),
                description=deposit_data.get('description', 'Depósito'),
                source=parsed_data.get('broker', 'CSV')
            )
            
            db.session.add(transaction)
            self.stats['deposits_created'] += 1
        
        for withdrawal_data in parsed_data.get('withdrawals', []):
            # Determinar fecha (con fallback) y convertir a datetime
            withdrawal_date_raw = withdrawal_data.get('date') or withdrawal_data.get('date_time')
            withdrawal_date = parse_datetime(withdrawal_date_raw)
            
            # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
            if not withdrawal_date:
                print(f"   ⚠️  ADVERTENCIA: Retiro sin fecha - Saltado")
                continue
            
            transaction = Transaction(
                user_id=self.user_id,
                account_id=self.broker_account_id,
                asset_id=None,
                transaction_type='WITHDRAWAL',
                transaction_date=withdrawal_date,
                settlement_date=withdrawal_date,
                quantity=None,
                price=None,
                amount=float(withdrawal_data['amount']),
                currency=withdrawal_data.get('currency', 'EUR'),
                description=withdrawal_data.get('description', 'Retiro'),
                source=parsed_data.get('broker', 'CSV')
            )
            
            db.session.add(transaction)
            self.stats['withdrawals_created'] += 1
    
    def _recalculate_holdings(self):
        """Recalcula holdings con FIFO robusto"""
        print(f"\n🔄 Recalculando holdings con FIFO robusto...")
        
        # Hacer flush para que las transacciones recién creadas sean visibles en queries
        # (pero NO commit, solo flush)
        db.session.flush()
        
        # Borrar holdings existentes
        PortfolioHolding.query.filter_by(
            user_id=self.user_id,
            account_id=self.broker_account_id
        ).delete()
        
        # Obtener todas las transacciones ordenadas (incluyendo las recién creadas)
        transactions = Transaction.query.filter_by(
            user_id=self.user_id,
            account_id=self.broker_account_id
        ).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).order_by(Transaction.transaction_date).all()
        
        print(f"   📝 Procesando {len(transactions)} transacciones...")
        
        # Agrupar por asset
        positions = {}
        for txn in transactions:
            if txn.asset_id not in positions:
                asset = Asset.query.get(txn.asset_id)
                positions[txn.asset_id] = FIFOCalculator(asset.symbol if asset else f'Asset_{txn.asset_id}')
            
            fifo = positions[txn.asset_id]
            
            if txn.transaction_type == 'BUY':
                fifo.add_buy(
                    date=txn.transaction_date,
                    quantity=txn.quantity,
                    price=txn.price,
                    total_cost=abs(txn.amount) + txn.commission + txn.fees + txn.tax
                )
            elif txn.transaction_type == 'SELL':
                fifo.add_sell(
                    quantity=txn.quantity,
                    date=txn.transaction_date
                )
        
        # Crear holdings solo para posiciones abiertas
        holdings_created = 0
        for asset_id, fifo in positions.items():
            position = fifo.get_current_position()
            
            if position['quantity'] > 0:
                holding = PortfolioHolding(
                    user_id=self.user_id,
                    account_id=self.broker_account_id,
                    asset_id=asset_id,
                    quantity=position['quantity'],
                    average_buy_price=position['average_buy_price'],
                    total_cost=position['total_cost'],
                    first_purchase_date=position['first_purchase_date'],
                    last_transaction_date=position['last_transaction_date']
                )
                
                db.session.add(holding)
                holdings_created += 1
        
        print(f"   ✅ {holdings_created} holdings creados (solo posiciones abiertas)")
        self.stats['holdings_created'] = holdings_created
    
    def _cleanup_zero_holdings(self):
        """Elimina holdings con cantidad <= 0"""
        deleted = PortfolioHolding.query.filter_by(
            user_id=self.user_id,
            account_id=self.broker_account_id
        ).filter(
            PortfolioHolding.quantity <= 0
        ).delete()
        
        if deleted > 0:
            print(f"   🗑️  {deleted} holdings con cantidad <= 0 eliminados")

