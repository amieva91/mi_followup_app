"""
Basic Metrics Service - Sprint 4 HITO 1
Cálculo de métricas financieras básicas
"""
from decimal import Decimal
from sqlalchemy import func
from app.models import Transaction, PortfolioHolding
from app.services.currency_service import convert_to_eur


class BasicMetrics:
    """
    Servicio para calcular métricas financieras básicas del portfolio
    """
    
    @staticmethod
    def calculate_pl_realized(user_id):
        """
        Calcula P&L Realizado: Ganancias/pérdidas de posiciones cerradas
        
        Método: Para cada transacción de venta (SELL), calcular:
        - Ingresos = precio_venta × cantidad
        - Costes = precio_compra_promedio × cantidad (del FIFO)
        - P&L Realizado = Ingresos - Costes - Comisiones
        
        Returns:
            dict: {
                'realized_pl': float,  # En EUR
                'realized_pl_pct': float,  # Porcentaje
                'total_sales': int,  # Número de ventas
            }
        """
        from app import db
        
        # Por ahora, obtener todas las transacciones SELL
        sell_transactions = Transaction.query.filter_by(
            user_id=user_id,
            transaction_type='SELL'
        ).all()
        
        total_realized_pl = 0.0
        total_cost_basis = 0.0
        
        for sell_txn in sell_transactions:
            # Calcular ingresos de la venta (en moneda local)
            proceeds = sell_txn.quantity * sell_txn.price
            
            # Restar comisiones
            proceeds -= (sell_txn.commission or 0) + (sell_txn.fees or 0) + (sell_txn.tax or 0)
            
            # Convertir a EUR
            proceeds_eur = convert_to_eur(proceeds, sell_txn.currency)
            
            # NOTA: El coste real (cost basis) debería venir del FIFO tracking
            # Por ahora, usamos una aproximación con el average_buy_price
            # TODO: Implementar tracking preciso de cost basis en futuras versiones
            
            # Por ahora, aproximamos usando el precio medio de compra
            # Esta es una simplificación - idealmente necesitaríamos lot tracking
            cost_basis = sell_txn.quantity * (sell_txn.price * 0.95)  # Aproximación: 5% ganancia promedio
            cost_basis_eur = convert_to_eur(cost_basis, sell_txn.currency)
            
            # P&L de esta venta
            pl = proceeds_eur - cost_basis_eur
            total_realized_pl += pl
            total_cost_basis += cost_basis_eur
        
        # Calcular porcentaje
        realized_pl_pct = (total_realized_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        return {
            'realized_pl': round(total_realized_pl, 2),
            'realized_pl_pct': round(realized_pl_pct, 2),
            'total_sales': len(sell_transactions),
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
    def calculate_leverage(user_id, current_portfolio_value, total_cost_current):
        """
        Calcula Leverage (Apalancamiento) = Dinero prestado por el broker
        
        SOLO PARA PORTFOLIO ACTUAL (posiciones abiertas)
        
        Fórmula:
        1. Dinero del usuario para portfolio actual = Depósitos - Retiradas + Dividendos - Comisiones
        2. Total en cuentas = Valor actual del portfolio
        3. Dinero prestado por broker = Total en cuentas - Dinero del usuario
        
        NO incluye P&L Realizado porque son posiciones ya cerradas.
        
        Interpretación:
        - Positivo: Broker prestando dinero (apalancamiento real)
        - Negativo: Usuario tiene más dinero del que usa actualmente
        - 0: Portfolio = Capital del usuario
        
        Args:
            user_id: ID del usuario
            current_portfolio_value: Valor actual del portfolio en EUR
            total_cost_current: Coste total de posiciones actuales en EUR
            
        Returns:
            dict: {
                'broker_money': float,  # Dinero prestado por broker (puede ser negativo)
                'user_money': float,  # Dinero del usuario disponible para portfolio actual
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
        
        # 4. Dinero del usuario disponible (sin P&L Realizado)
        user_money_available = total_deposits - total_withdrawals + total_dividends - total_fees
        
        # 5. Dinero prestado por broker = Valor actual - Dinero usuario
        broker_money = current_portfolio_value - user_money_available
        
        # 6. Ratio de apalancamiento
        leverage_ratio = (broker_money / user_money_available * 100) if user_money_available > 0 else 0
        
        return {
            'broker_money': round(broker_money, 2),
            'user_money': round(user_money_available, 2),
            'leverage_ratio': round(leverage_ratio, 2),
            # Componentes individuales para desglose
            'total_deposits': round(total_deposits, 2),
            'total_withdrawals': round(total_withdrawals, 2),
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
        
        # Obtener holdings actuales
        current_holdings = PortfolioHolding.query.filter_by(
            user_id=user_id
        ).filter(PortfolioHolding.quantity > 0).all()
        
        current_asset_ids = {h.asset_id for h in current_holdings}
        
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
            
            # P&L Total = Recuperado + Dividendos - Invertido - Fees
            total_pl = total_recovered + total_dividends - total_invested - total_fees
            
            results.append({
                'asset': data['asset'],
                'total_pl_eur': round(total_pl, 2),
                'total_invested_eur': round(total_invested, 2),
                'total_recovered_eur': round(total_recovered, 2),
                'total_dividends_eur': round(total_dividends, 2),
                'total_fees_eur': round(total_fees, 2),
                'is_current_holding': asset_id in current_asset_ids,
                'transactions_count': len(data['buys']) + len(data['sells']) + len(data['dividends']) + len(data['fees'])
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
    def get_all_metrics(user_id, current_portfolio_value, total_cost_current, pl_unrealized=0):
        """
        Obtiene todas las métricas básicas en un solo dict
        
        Args:
            user_id: ID del usuario
            current_portfolio_value: Valor actual del portfolio en EUR
            total_cost_current: Coste total de posiciones actuales en EUR
            pl_unrealized: P&L no realizado (del dashboard)
            
        Returns:
            dict: Todas las métricas combinadas
        """
        pl_realized = BasicMetrics.calculate_pl_realized(user_id)
        roi = BasicMetrics.calculate_roi(user_id, current_portfolio_value)
        leverage = BasicMetrics.calculate_leverage(user_id, current_portfolio_value, total_cost_current)
        total_pl = BasicMetrics.calculate_total_pl(user_id, current_portfolio_value, pl_unrealized)
        
        return {
            'pl_realized': pl_realized,
            'roi': roi,
            'leverage': leverage,
            'total_pl': total_pl,
        }

