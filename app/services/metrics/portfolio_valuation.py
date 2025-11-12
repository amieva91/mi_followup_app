"""
Portfolio Valuation Service

Calcula el valor del portfolio en cualquier fecha usando:
- Transacciones históricas (FIFO)
- Precios de compra/venta
- Precios actuales (solo para holdings actuales)
"""

from datetime import datetime
from app.models.transaction import Transaction
from app.models.asset import Asset
from app.services.fifo_calculator import FIFOCalculator
from app.services.currency_service import convert_to_eur


class PortfolioValuation:
    """
    Servicio para valorar el portfolio en cualquier momento
    """
    
    @staticmethod
    def get_value_at_date(user_id, target_date, use_current_prices=False):
        """
        Calcula el valor total del portfolio en una fecha específica
        
        Args:
            user_id: ID del usuario
            target_date: Fecha objetivo (datetime)
            use_current_prices: Si True, usa asset.current_price para holdings actuales
                               Solo aplica si target_date es HOY
        
        Returns:
            float: Valor total del portfolio en EUR
        """
        # 1. Obtener todas las transacciones hasta la fecha objetivo
        transactions = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date <= target_date
        ).order_by(Transaction.transaction_date).all()
        
        # 2. Reconstruir estado del portfolio con FIFO
        fifo_calculators = {}  # {asset_id: FIFOCalculator}
        cash_balance = 0.0
        
        for txn in transactions:
            asset_id = txn.asset_id if txn.asset_id else None
            
            # DEPOSIT: Añade cash
            if txn.transaction_type == 'DEPOSIT':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance += amount_eur
            
            # WITHDRAWAL: Quita cash
            elif txn.transaction_type == 'WITHDRAWAL':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance -= amount_eur
            
            # BUY: Compra activo (quita cash, añade holding)
            elif txn.transaction_type == 'BUY' and asset_id:
                # Coste total = precio × cantidad + comisiones + fees + tax
                total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
                cost_eur = convert_to_eur(total_cost, txn.currency)
                cash_balance -= cost_eur
                
                # Registrar compra en FIFO
                if asset_id not in fifo_calculators:
                    asset_symbol = txn.asset.symbol if txn.asset else f"Asset_{asset_id}"
                    fifo_calculators[asset_id] = FIFOCalculator(symbol=asset_symbol)
                
                fifo_calculators[asset_id].add_buy(
                    quantity=txn.quantity,
                    price=txn.price,
                    date=txn.transaction_date,
                    total_cost=total_cost
                )
            
            # SELL: Vende activo (añade cash, quita holding)
            elif txn.transaction_type == 'SELL' and asset_id:
                # Ingresos = precio × cantidad - comisiones - fees - tax
                proceeds = (txn.quantity * txn.price) - txn.commission - txn.fees - txn.tax
                proceeds_eur = convert_to_eur(proceeds, txn.currency)
                cash_balance += proceeds_eur
                
                # Actualizar FIFO (quitar holdings vendidos)
                if asset_id in fifo_calculators:
                    fifo_calculators[asset_id].add_sell(
                        quantity=txn.quantity,
                        date=txn.transaction_date
                    )
            
            # DIVIDEND: Añade cash
            elif txn.transaction_type == 'DIVIDEND':
                dividend_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance += dividend_eur
            
            # FEE: Quita cash
            elif txn.transaction_type == 'FEE':
                fee_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance -= fee_eur
        
        # 3. Calcular valor de holdings actuales y P&L No Realizado
        holdings_value = 0.0
        holdings_cost = 0.0  # Nuevo: Coste total de holdings actuales
        today = datetime.now().date()
        is_today = (target_date.date() >= today)

        for asset_id, fifo in fifo_calculators.items():
            position = fifo.get_current_position()
            current_quantity = position['quantity']

            # Si no hay holdings, skip
            if current_quantity <= 0:
                continue

            # Obtener asset
            asset = Asset.query.get(asset_id)
            if not asset:
                continue

            # Decidir qué precio usar
            if use_current_prices and is_today and asset.current_price:
                # Para HOY con precios actualizados: usar precio de mercado
                price = asset.current_price
            else:
                # Para histórico o sin precios actuales: usar precio medio de compra
                price = position['average_buy_price']

            # Calcular valor en moneda local
            value_local = current_quantity * price
            cost_local = current_quantity * position['average_buy_price']

            # Convertir a EUR
            value_eur = convert_to_eur(value_local, asset.currency)
            cost_eur = convert_to_eur(cost_local, asset.currency)
            
            holdings_value += value_eur
            holdings_cost += cost_eur

        # 4. Valor total = cash + holdings
        total_value = cash_balance + holdings_value

        return total_value
    
    @staticmethod
    def get_detailed_value_at_date(user_id, target_date, use_current_prices=False):
        """
        Versión mejorada que devuelve desglose completo del portfolio
        
        Returns:
            dict: {
                'total_value': float,
                'cash_balance': float,
                'holdings_value': float,
                'holdings_cost': float,
                'pl_unrealized': float
            }
        """
        # Reutilizar la misma lógica que get_value_at_date
        transactions = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date <= target_date
        ).order_by(Transaction.transaction_date).all()

        fifo_calculators = {}
        cash_balance = 0.0

        for txn in transactions:
            asset_id = txn.asset_id if txn.asset_id else None

            if txn.transaction_type == 'DEPOSIT':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance += amount_eur
            elif txn.transaction_type == 'WITHDRAWAL':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance -= amount_eur
            elif txn.transaction_type == 'BUY' and asset_id:
                total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
                cost_eur = convert_to_eur(total_cost, txn.currency)
                cash_balance -= cost_eur

                if asset_id not in fifo_calculators:
                    asset_symbol = txn.asset.symbol if txn.asset else f"Asset_{asset_id}"
                    fifo_calculators[asset_id] = FIFOCalculator(symbol=asset_symbol)

                fifo_calculators[asset_id].add_buy(
                    quantity=txn.quantity,
                    price=txn.price,
                    date=txn.transaction_date,
                    total_cost=total_cost
                )
            elif txn.transaction_type == 'SELL' and asset_id:
                proceeds = (txn.quantity * txn.price) - txn.commission - txn.fees - txn.tax
                proceeds_eur = convert_to_eur(proceeds, txn.currency)
                cash_balance += proceeds_eur

                if asset_id in fifo_calculators:
                    fifo_calculators[asset_id].add_sell(
                        quantity=txn.quantity,
                        date=txn.transaction_date
                    )
            elif txn.transaction_type == 'DIVIDEND':
                dividend_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance += dividend_eur
            elif txn.transaction_type == 'FEE':
                fee_eur = convert_to_eur(abs(txn.amount), txn.currency)
                cash_balance -= fee_eur

        # Calcular valores de holdings
        holdings_value = 0.0
        holdings_cost = 0.0
        today = datetime.now().date()
        is_today = (target_date.date() >= today)

        for asset_id, fifo in fifo_calculators.items():
            position = fifo.get_current_position()
            current_quantity = position['quantity']

            if current_quantity <= 0:
                continue

            asset = Asset.query.get(asset_id)
            if not asset:
                continue

            if use_current_prices and is_today and asset.current_price:
                price = asset.current_price
            else:
                price = position['average_buy_price']

            value_local = current_quantity * price
            cost_local = current_quantity * position['average_buy_price']

            value_eur = convert_to_eur(value_local, asset.currency)
            cost_eur = convert_to_eur(cost_local, asset.currency)
            
            holdings_value += value_eur
            holdings_cost += cost_eur

        pl_unrealized = holdings_value - holdings_cost
        total_value = cash_balance + holdings_value

        return {
            'total_value': total_value,
            'cash_balance': cash_balance,
            'holdings_value': holdings_value,
            'holdings_cost': holdings_cost,
            'pl_unrealized': pl_unrealized
        }

    @staticmethod
    def get_user_money_at_date(user_id, target_date):
        """
        Calcula cuánto dinero REAL tiene el usuario en una fecha
        (sin contar apalancamiento)
        
        Formula:
        Dinero Usuario = Deposits - Withdrawals + P&L Realizado + P&L No Realizado 
                        + Dividends - Fees
        
        Args:
            user_id: ID del usuario
            target_date: Fecha objetivo (datetime)
        
        Returns:
            float: Dinero real del usuario en EUR
        """
        # Obtener todas las transacciones hasta la fecha
        transactions = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date <= target_date
        ).order_by(Transaction.transaction_date).all()
        
        total_deposits = 0.0
        total_withdrawals = 0.0
        total_dividends = 0.0
        total_fees = 0.0
        
        # Reconstruir FIFO para calcular P&L realizado
        fifo_calculators = {}
        pl_realized = 0.0
        
        for txn in transactions:
            asset_id = txn.asset_id if txn.asset_id else None
            
            if txn.transaction_type == 'DEPOSIT':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                total_deposits += amount_eur
            
            elif txn.transaction_type == 'WITHDRAWAL':
                amount_eur = convert_to_eur(abs(txn.amount), txn.currency)
                total_withdrawals += amount_eur
            
            elif txn.transaction_type == 'DIVIDEND':
                dividend_eur = convert_to_eur(abs(txn.amount), txn.currency)
                total_dividends += dividend_eur
            
            elif txn.transaction_type in ['FEE', 'BUY', 'SELL']:
                # Sumar comisiones de todas las operaciones
                fees = txn.commission + txn.fees + txn.tax
                fees_eur = convert_to_eur(fees, txn.currency)
                total_fees += fees_eur
                
                # Para BUY/SELL: calcular P&L realizado con FIFO
                if txn.transaction_type == 'BUY' and asset_id:
                    if asset_id not in fifo_calculators:
                        symbol = txn.asset.symbol if txn.asset else f"Asset_{asset_id}"
                        fifo_calculators[asset_id] = FIFOCalculator(symbol=symbol)
                    
                    total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
                    fifo_calculators[asset_id].add_buy(
                        quantity=txn.quantity,
                        price=txn.price,
                        date=txn.transaction_date,
                        total_cost=total_cost
                    )
                
                elif txn.transaction_type == 'SELL' and asset_id:
                    proceeds = (txn.quantity * txn.price) - txn.commission - txn.fees - txn.tax
                    proceeds_eur = convert_to_eur(proceeds, txn.currency)
                    
                    if asset_id in fifo_calculators:
                        cost_basis = float(fifo_calculators[asset_id].add_sell(
                            quantity=txn.quantity,
                            date=txn.transaction_date
                        ))
                        cost_basis_eur = convert_to_eur(cost_basis, txn.currency)
                        
                        # P&L de esta venta
                        pl_eur = proceeds_eur - cost_basis_eur
                        pl_realized += pl_eur
        
        # Calcular P&L No Realizado (holdings actuales)
        pl_unrealized = 0.0
        today = datetime.now().date()
        is_today = (target_date.date() >= today)
        
        for asset_id, fifo in fifo_calculators.items():
            position = fifo.get_current_position()
            current_quantity = position['quantity']
            if current_quantity <= 0:
                continue
            
            asset = Asset.query.get(asset_id)
            if not asset:
                continue
            
            # Solo usar precio actual si es HOY
            if is_today and asset.current_price:
                current_value_local = current_quantity * asset.current_price
                current_value_eur = convert_to_eur(current_value_local, asset.currency)
                
                current_cost = position['total_cost']
                current_cost_eur = convert_to_eur(current_cost, asset.currency)
                
                pl_unrealized += (current_value_eur - current_cost_eur)
        
        # Dinero total del usuario
        user_money = (
            total_deposits 
            - total_withdrawals 
            + pl_realized 
            + pl_unrealized 
            + total_dividends 
            - total_fees
        )
        
        return user_money

