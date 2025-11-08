"""
Basic Metrics Service - Sprint 4 HITO 1
Cálculo de métricas financieras básicas
"""
from decimal import Decimal
from sqlalchemy import func
from app.models import Transaction, PortfolioHolding
from app.services.currency_service import convert_to_eur
from app.services.fifo_calculator import FIFOCalculator
from collections import defaultdict


class BasicMetrics:
    """
    Servicio para calcular métricas financieras básicas del portfolio
    """
    
    @staticmethod
    def calculate_pl_realized(user_id):
        """
        Calcula P&L Realizado: Ganancias/pérdidas de posiciones cerradas usando FIFO real
        
        Método: Para cada asset:
        1. Procesar todas las transacciones BUY/SELL en orden cronológico con FIFO
        2. Para cada venta, obtener el coste real de los lotes vendidos (FIFO)
        3. P&L Realizado = Ingresos venta - Coste real FIFO
        
        Returns:
            dict: {
                'realized_pl': float,  # En EUR
                'realized_pl_pct': float,  # Porcentaje
                'total_sales': int,  # Número de ventas
            }
        """
        # Obtener TODAS las transacciones BUY/SELL por asset, en orden cronológico
        transactions = Transaction.query.filter_by(user_id=user_id).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).order_by(Transaction.transaction_date, Transaction.created_at).all()
        
        # Agrupar por asset
        asset_transactions = defaultdict(list)
        for txn in transactions:
            if txn.asset_id:
                asset_transactions[txn.asset_id].append(txn)
        
        total_realized_pl_eur = 0.0
        total_cost_basis_eur = 0.0
        total_sales_count = 0
        
        # Procesar cada asset con FIFO
        for asset_id, txns in asset_transactions.items():
            fifo = FIFOCalculator(symbol=f"Asset_{asset_id}")
            
            for txn in txns:
                if txn.transaction_type == 'BUY':
                    # Coste total de la compra (precio + comisiones)
                    total_cost = (txn.quantity * txn.price) + \
                                (txn.commission or 0) + \
                                (txn.fees or 0) + \
                                (txn.tax or 0)
                    
                    fifo.add_buy(
                        quantity=txn.quantity,
                        price=txn.price,
                        date=txn.transaction_date,
                        total_cost=total_cost
                    )
                
                elif txn.transaction_type == 'SELL':
                    # Ingresos de la venta (después de comisiones/fees)
                    proceeds = (txn.quantity * txn.price) - \
                              (txn.commission or 0) - \
                              (txn.fees or 0) - \
                              (txn.tax or 0)
                    proceeds_eur = convert_to_eur(proceeds, txn.currency)
                    
                    # Obtener el coste real de lo vendido usando FIFO
                    cost_basis = float(fifo.add_sell(
                        quantity=txn.quantity,
                        date=txn.transaction_date
                    ))
                    cost_basis_eur = convert_to_eur(cost_basis, txn.currency)
                    
                    # P&L de esta venta
                    pl_eur = proceeds_eur - cost_basis_eur
                    
                    total_realized_pl_eur += pl_eur
                    total_cost_basis_eur += cost_basis_eur
                    total_sales_count += 1
        
        # Calcular porcentaje
        realized_pl_pct = (total_realized_pl_eur / total_cost_basis_eur * 100) if total_cost_basis_eur > 0 else 0
        
        return {
            'realized_pl': round(total_realized_pl_eur, 2),
            'realized_pl_pct': round(realized_pl_pct, 2),
            'total_sales': total_sales_count,
        }
    
    @staticmethod
    def calculate_roi(user_id, current_portfolio_value):
        """
        Calcula ROI (Return on Investment)
        
        Fórmula: ROI = (Valor Actual + Retiradas - Depósitos) / Depósitos × 100
        
        Args:
            user_id: ID del usuario
            current_portfolio_value: Valor actual del portfolio en EUR
            
        Returns:
            dict: {
                'roi': float,  # Porcentaje
                'total_deposits': float,  # En EUR
                'total_withdrawals': float,  # En EUR
                'net_invested': float,  # Depósitos - Retiradas
                'absolute_return': float,  # Ganancia/Pérdida absoluta
            }
        """
        # Obtener todos los depósitos
        deposits = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='DEPOSIT'
        ).all()
        
        total_deposits = 0.0
        for dep in deposits:
            amount_eur = convert_to_eur(abs(dep.amount), dep.currency)
            total_deposits += amount_eur
        
        # Obtener todos los retiros
        withdrawals = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='WITHDRAWAL'
        ).all()
        
        total_withdrawals = 0.0
        for wit in withdrawals:
            amount_eur = convert_to_eur(abs(wit.amount), wit.currency)
            total_withdrawals += amount_eur
        
        # Capital neto invertido
        net_invested = total_deposits - total_withdrawals
        
        # Retorno absoluto
        absolute_return = current_portfolio_value + total_withdrawals - total_deposits
        
        # ROI %
        roi = (absolute_return / total_deposits * 100) if total_deposits > 0 else 0
        
        return {
            'roi': round(roi, 2),
            'total_deposits': round(total_deposits, 2),
            'total_withdrawals': round(total_withdrawals, 2),
            'net_invested': round(net_invested, 2),
            'absolute_return': round(absolute_return, 2),
        }
    
    @staticmethod
    def calculate_leverage(user_id, current_portfolio_value, total_cost_current, pl_unrealized):
        """
        Calcula Leverage (Apalancamiento) = Dinero prestado por el broker
        
        SOLO PARA PORTFOLIO ACTUAL (posiciones abiertas)
        
        Fórmula:
        1. Dinero del usuario = Depósitos - Retiradas + P&L No Realizado + Dividendos - Comisiones
        2. Total en cuentas = Valor actual del portfolio
        3. Dinero prestado por broker = Total en cuentas - Dinero del usuario
        
        INCLUYE P&L No Realizado porque son ganancias del usuario en las posiciones actuales.
        NO incluye P&L Realizado (posiciones cerradas).
        
        Interpretación:
        - Positivo: Broker prestando dinero (apalancamiento real)
        - Negativo: Usuario tiene más dinero del que necesita
        - 0: Portfolio = Capital del usuario
        
        Args:
            user_id: ID del usuario
            current_portfolio_value: Valor actual del portfolio en EUR
            total_cost_current: Coste total de posiciones actuales en EUR
            pl_unrealized: P&L no realizado (ganancias de posiciones abiertas)
            
        Returns:
            dict: {
                'broker_money': float,  # Dinero prestado por broker (puede ser negativo)
                'user_money': float,  # Dinero del usuario (incluye ganancias actuales)
                'leverage_ratio': float,  # Ratio de apalancamiento
            }
        """
        # 1. Obtener depósitos y retiradas
        deposits = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='DEPOSIT'
        ).all()
        
        total_deposits = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits)
        
        withdrawals = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='WITHDRAWAL'
        ).all()
        
        total_withdrawals = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals)
        
        # 2. Obtener dividendos (todo el histórico)
        dividends = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='DIVIDEND'
        ).all()
        
        total_dividends = sum(convert_to_eur(abs(d.amount), d.currency) for d in dividends)
        
        # 3. Obtener comisiones/fees (todo el histórico)
        fees = Transaction.query.filter_by(user_id=user_id).filter(
            Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
        ).all()
        
        total_fees = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees)
        
        # 4. Obtener P&L Realizado
        pl_realized_data = BasicMetrics.calculate_pl_realized(user_id)
        pl_realized = pl_realized_data['realized_pl']
        
        # 5. Dinero del usuario (INCLUYE P&L Realizado + P&L No Realizado)
        user_money = total_deposits - total_withdrawals + pl_realized + pl_unrealized + total_dividends - total_fees
        
        # 5. Dinero prestado por broker = Valor actual - Dinero usuario
        broker_money = current_portfolio_value - user_money
        
        # 6. Ratio de apalancamiento
        leverage_ratio = (broker_money / user_money * 100) if user_money > 0 else 0
        
        return {
            'broker_money': round(broker_money, 2),
            'user_money': round(user_money, 2),
            'leverage_ratio': round(leverage_ratio, 2),
            # Componentes individuales para desglose
            'total_deposits': round(total_deposits, 2),
            'total_withdrawals': round(total_withdrawals, 2),
            'pl_realized': round(pl_realized, 2),
            'pl_unrealized': round(pl_unrealized, 2),
            'total_dividends': round(total_dividends, 2),
            'total_fees': round(total_fees, 2),
        }
    
    @staticmethod
    def get_pl_by_asset(user_id):
        """
        Calcula P&L histórico total por cada asset
        
        Para cada asset, suma:
        - BUY: -total (inversión inicial)
        - SELL: +total (recuperación + ganancia)
        - DIVIDEND: +amount (ingresos)
        - FEE/COMMISSION: -amount (costes)
        
        Returns:
            list: [{
                'asset': Asset object,
                'total_pl_eur': float,
                'total_invested_eur': float,
                'total_recovered_eur': float,
                'total_dividends_eur': float,
                'total_fees_eur': float,
                'is_current_holding': bool,
                'transactions_count': int
            }]
        """
        from collections import defaultdict
        
        # Obtener todas las transacciones del usuario
        transactions = Transaction.query.filter_by(user_id=user_id).all()
        
        # Agrupar por asset
        by_asset = defaultdict(lambda: {
            'asset': None,
            'buys': [],
            'sells': [],
            'dividends': [],
            'fees': [],
            'is_current_holding': False
        })
        
        for txn in transactions:
            if not txn.asset_id:
                continue
            
            asset_id = txn.asset_id
            if by_asset[asset_id]['asset'] is None:
                by_asset[asset_id]['asset'] = txn.asset
            
            if txn.transaction_type == 'BUY':
                by_asset[asset_id]['buys'].append(txn)
            elif txn.transaction_type == 'SELL':
                by_asset[asset_id]['sells'].append(txn)
            elif txn.transaction_type == 'DIVIDEND':
                by_asset[asset_id]['dividends'].append(txn)
            elif txn.transaction_type in ['FEE', 'COMMISSION']:
                by_asset[asset_id]['fees'].append(txn)
        
        # Obtener holdings actuales con sus valores
        current_holdings = PortfolioHolding.query.filter_by(
            user_id=user_id
        ).filter(PortfolioHolding.quantity > 0).all()
        
        current_asset_ids = {h.asset_id for h in current_holdings}
        
        # Crear diccionario de valores actuales por asset
        current_values = {}
        current_costs = {}
        for h in current_holdings:
            current_value = h.quantity * (h.current_price or 0)
            current_value_eur = convert_to_eur(current_value, h.asset.currency if h.asset else 'EUR')
            
            total_cost = h.total_cost or (h.quantity * (h.average_buy_price or 0))
            total_cost_eur = convert_to_eur(total_cost, h.asset.currency if h.asset else 'EUR')
            
            current_values[h.asset_id] = current_value_eur
            current_costs[h.asset_id] = total_cost_eur
        
        # Calcular P&L por asset
        results = []
        
        for asset_id, data in by_asset.items():
            total_invested = 0  # Lo que gastamos comprando
            total_recovered = 0  # Lo que recuperamos vendiendo
            total_dividends = 0  # Dividendos recibidos
            total_fees = 0  # Comisiones pagadas
            
            # Compras (inversión)
            for txn in data['buys']:
                cost = txn.quantity * txn.price
                cost += (txn.commission or 0) + (txn.fees or 0) + (txn.tax or 0)
                total_invested += convert_to_eur(cost, txn.currency)
            
            # Ventas (recuperación)
            for txn in data['sells']:
                proceeds = txn.quantity * txn.price
                proceeds -= (txn.commission or 0) + (txn.fees or 0) + (txn.tax or 0)
                total_recovered += convert_to_eur(proceeds, txn.currency)
            
            # Dividendos
            for txn in data['dividends']:
                total_dividends += convert_to_eur(abs(txn.amount), txn.currency)
            
            # Comisiones
            for txn in data['fees']:
                total_fees += convert_to_eur(abs(txn.amount), txn.currency)
            
            # Calcular P&L según si es posición actual o cerrada
            is_current = asset_id in current_asset_ids
            
            if is_current:
                # Para posiciones actuales: P&L = Valor actual - Coste + Dividendos - Fees
                current_value = current_values.get(asset_id, 0)
                current_cost = current_costs.get(asset_id, 0)
                total_pl = current_value - current_cost + total_dividends - total_fees
            else:
                # Para posiciones cerradas: P&L = Recuperado + Dividendos - Invertido - Fees
                total_pl = total_recovered + total_dividends - total_invested - total_fees
            
            results.append({
                'asset': data['asset'],
                'total_pl_eur': round(total_pl, 2),
                'total_invested_eur': round(total_invested, 2),
                'total_recovered_eur': round(total_recovered, 2),
                'total_dividends_eur': round(total_dividends, 2),
                'total_fees_eur': round(total_fees, 2),
                'is_current_holding': asset_id in current_asset_ids,
                'transactions_count': len(data['buys']) + len(data['sells']) + len(data['dividends']) + len(data['fees']),
                'dividends_count': len(data['dividends'])
            })
        
        # Ordenar por P&L descendente
        results.sort(key=lambda x: x['total_pl_eur'], reverse=True)
        
        return results
    
    @staticmethod
    def calculate_total_pl(user_id, current_portfolio_value, pl_unrealized):
        """
        Calcula P&L TOTAL histórico = P&L Realizado + P&L No Realizado
        
        Args:
            user_id: ID del usuario
            current_portfolio_value: Valor actual del portfolio en EUR
            pl_unrealized: P&L no realizado (del dashboard)
            
        Returns:
            dict: {
                'total_pl': float,  # P&L total en EUR
                'total_pl_pct': float,  # Porcentaje sobre capital total
                'pl_realized': float,  # Componente realizado
                'pl_unrealized': float,  # Componente no realizado
            }
        """
        # Obtener depósitos totales
        deposits = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='DEPOSIT'
        ).all()
        
        total_deposits = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits)
        
        # Obtener retiradas totales
        withdrawals = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='WITHDRAWAL'
        ).all()
        
        total_withdrawals = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals)
        
        # Capital neto invertido
        net_capital = total_deposits - total_withdrawals
        
        # P&L Realizado (aproximación simplificada)
        sells = Transaction.query.filter_by(user_id=user_id, transaction_type='SELL').all()
        buys = Transaction.query.filter_by(user_id=user_id, transaction_type='BUY').all()
        
        total_sells_proceeds = sum(
            convert_to_eur(
                s.quantity * s.price - (s.commission or 0) - (s.fees or 0) - (s.tax or 0),
                s.currency
            ) for s in sells
        )
        
        total_buys_cost = sum(
            convert_to_eur(
                b.quantity * b.price + (b.commission or 0) + (b.fees or 0) + (b.tax or 0),
                b.currency
            ) for b in buys
        )
        
        pl_realized = total_sells_proceeds - total_buys_cost
        
        # P&L Total = Realizado + No Realizado
        total_pl = pl_realized + pl_unrealized
        
        # Porcentaje sobre capital neto
        total_pl_pct = (total_pl / net_capital * 100) if net_capital > 0 else 0
        
        return {
            'total_pl': round(total_pl, 2),
            'total_pl_pct': round(total_pl_pct, 2),
            'pl_realized': round(pl_realized, 2),
            'pl_unrealized': round(pl_unrealized, 2),
        }
    
    @staticmethod
    def calculate_total_account_value(user_id):
        """
        Calcula Valor Total de la Cuenta de Inversión
        
        Este valor representa TODO el dinero del usuario en la cuenta:
        - Lo invertido en activos (valor actual)
        - El cash disponible (si lo hay)
        
        Fórmula:
        Valor Total Cuenta = Depósitos - Retiradas + P&L Realizado + P&L No Realizado + Dividendos - Comisiones
        
        Componentes:
        - Depósitos: Dinero aportado por el usuario
        - Retiradas: Dinero retirado por el usuario
        - P&L Realizado: Ganancias/pérdidas de posiciones cerradas
        - P&L No Realizado: Ganancias/pérdidas de posiciones actuales
        - Dividendos: Ingresos por dividendos
        - Comisiones: Costes pagados al broker
        
        Returns:
            dict: {
                'total_account_value': float,  # Valor total en EUR
                'deposits': float,
                'withdrawals': float,
                'pl_realized': float,
                'pl_unrealized': float,
                'dividends': float,
                'fees': float,
            }
        """
        # Ya tenemos estos cálculos en calculate_leverage, los reutilizamos
        deposits = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='DEPOSIT'
        ).all()
        total_deposits = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits)
        
        withdrawals = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='WITHDRAWAL'
        ).all()
        total_withdrawals = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals)
        
        dividends = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='DIVIDEND'
        ).all()
        total_dividends = sum(convert_to_eur(abs(d.amount), d.currency) for d in dividends)
        
        fees = Transaction.query.filter_by(user_id=user_id).filter(
            Transaction.transaction_type.in_(['FEE', 'COMMISSION'])
        ).all()
        total_fees = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees)
        
        # Obtener P&L Realizado
        pl_realized_data = BasicMetrics.calculate_pl_realized(user_id)
        pl_realized = pl_realized_data['realized_pl']
        
        # Para obtener P&L No Realizado, necesitamos los holdings actuales
        # Lo pasaremos como parámetro desde get_all_metrics
        # Por ahora, retornamos None y lo calcularemos en get_all_metrics
        
        return {
            'deposits': round(total_deposits, 2),
            'withdrawals': round(total_withdrawals, 2),
            'pl_realized': round(pl_realized, 2),
            'dividends': round(total_dividends, 2),
            'fees': round(total_fees, 2),
        }
    
    @staticmethod
    def get_all_metrics(user_id, current_portfolio_value, total_cost_current, pl_unrealized=0):
        """
        Obtiene todas las métricas básicas en un solo dict
        
        Args:
            user_id: ID del usuario
            current_portfolio_value: Valor actual del portfolio en EUR (solo posiciones abiertas)
            total_cost_current: Coste total de posiciones actuales en EUR
            pl_unrealized: P&L no realizado (del dashboard)
            
        Returns:
            dict: Todas las métricas combinadas
        """
        pl_realized = BasicMetrics.calculate_pl_realized(user_id)
        roi = BasicMetrics.calculate_roi(user_id, current_portfolio_value)
        leverage = BasicMetrics.calculate_leverage(user_id, current_portfolio_value, total_cost_current, pl_unrealized)
        total_pl = BasicMetrics.calculate_total_pl(user_id, current_portfolio_value, pl_unrealized)
        
        # Calcular Valor Total Cuenta de Inversión
        account_components = BasicMetrics.calculate_total_account_value(user_id)
        total_account_value = (
            account_components['deposits'] -
            account_components['withdrawals'] +
            account_components['pl_realized'] +
            pl_unrealized +  # Este viene del dashboard
            account_components['dividends'] -
            account_components['fees']
        )
        account_components['pl_unrealized'] = round(pl_unrealized, 2)
        account_components['total_account_value'] = round(total_account_value, 2)
        account_components['cash_or_leverage'] = round(total_account_value - current_portfolio_value, 2)
        
        return {
            'pl_realized': pl_realized,
            'roi': roi,
            'leverage': leverage,
            'total_pl': total_pl,
            'total_account': account_components,
        }

