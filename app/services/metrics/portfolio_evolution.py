"""
Portfolio Evolution Service
Calcula la evolución histórica del portfolio para gráficos.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import func
from app import db
from app.models.transaction import Transaction
from app.models.portfolio import PortfolioHolding
from app.services.metrics.portfolio_valuation import PortfolioValuation
from app.services.metrics.modified_dietz import ModifiedDietzCalculator
from app.services.metrics.basic_metrics import BasicMetrics
from app.services.currency_service import convert_to_eur


class PortfolioEvolutionService:
    """Servicio para calcular la evolución histórica del portfolio"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
    
    def get_evolution_data(self, frequency: str = 'weekly') -> Dict[str, Any]:
        """
        Obtiene datos de evolución del portfolio para gráficos.
        
        Args:
            frequency: 'daily', 'weekly', 'monthly'
        
        Returns:
            Dict con labels y datasets para Chart.js
        """
        # Obtener rango de fechas
        first_transaction = Transaction.query.filter_by(user_id=self.user_id)\
            .order_by(Transaction.transaction_date.asc()).first()
        
        if not first_transaction:
            return self._empty_response()
        
        start_date = first_transaction.transaction_date.date()
        end_date = datetime.now().date()
        
        # Convertir start_date a datetime para Modified Dietz
        start_date_dt = datetime.combine(start_date, datetime.min.time())
        
        # Generar fechas según frecuencia
        dates = self._generate_dates(start_date, end_date, frequency)
        
        # Calcular valores del portfolio en cada fecha
        portfolio_values = []
        capital_invested = []
        returns_pct = []
        leverage_data = []  # Nuevo: Apalancamiento/Cash
        cash_flows_cumulative = []  # Nuevo: Flujos acumulados
        pl_accumulated = []  # Nuevo: P&L total acumulado
        
        for date in dates:
            # Obtener valores detallados del portfolio
            date_datetime = datetime.combine(date, datetime.max.time())
            portfolio_data = PortfolioValuation.get_detailed_value_at_date(
                user_id=self.user_id,
                target_date=date_datetime,
                use_current_prices=(date == end_date)
            )
            
            value = portfolio_data['total_value']
            holdings_value = portfolio_data['holdings_value']  # Nuevo: valor de acciones
            pl_unrealized_at_date = portfolio_data['pl_unrealized']
            
            portfolio_values.append(float(value))

            # Capital invertido neto (deposits - withdrawals)
            capital = self._get_capital_invested(date)
            capital_invested.append(float(capital))
            
            # Rentabilidad acumulada (Modified Dietz) - usar método estático
            date_datetime_end = datetime.combine(date, datetime.max.time())
            return_data = ModifiedDietzCalculator.calculate_return(
                user_id=self.user_id,
                start_date=start_date_dt,
                end_date=date_datetime_end
            )
            if return_data and return_data['return_pct'] is not None:
                returns_pct.append(float(return_data['return_pct']))
            else:
                returns_pct.append(0.0)
            
            # Nuevo: Apalancamiento/Cash y P&L
            # Obtener componentes para el cálculo
            dividends = self._get_dividends_until(date)
            fees = self._get_fees_until(date)
            pl_realized = self._get_pl_realized_until(date)
            
            # P&L No Realizado SOLO aplica al último punto (HOY) con precios actuales
            # Para fechas históricas, no tenemos precios de mercado, solo precio medio de compra
            if date == end_date:
                # HOY: Incluir P&L No Realizado (posiciones abiertas con precio actual)
                pl_total = pl_realized + pl_unrealized_at_date + dividends - fees
                user_money = float(capital) + pl_realized + pl_unrealized_at_date + dividends - fees
            else:
                # HISTÓRICO: Solo P&L Realizado (ventas completadas)
                pl_total = pl_realized + dividends - fees
                user_money = float(capital) + pl_realized + dividends - fees
            
            # Gráfico 3: Apalancamiento/Cash = Dinero del Usuario - Holdings Value
            # Si positivo: tienes cash sin invertir
            # Si negativo: has invertido más de lo que tienes (apalancamiento)
            broker_money = user_money - float(holdings_value)
            
            leverage_data.append(float(broker_money))
            
            # Nuevo: Flujos acumulados (capital invertido es la suma neta)
            cash_flows_cumulative.append(float(capital))
            
            # Nuevo: P&L Acumulado
            pl_accumulated.append(float(pl_total))
        
        # Obtener cash flows para marcadores
        cash_flows = self._get_cash_flows()
        
        return {
            'labels': [d.strftime('%Y-%m-%d') for d in dates],
            'datasets': {
                'portfolio_value': portfolio_values,
                'capital_invested': capital_invested,
                'returns_pct': returns_pct,
                'leverage': leverage_data,  # Nuevo: Apalancamiento/Cash
                'cash_flows_cumulative': cash_flows_cumulative,  # Nuevo: Flujos acumulados
                'pl_accumulated': pl_accumulated  # Nuevo: P&L total
            },
            'cash_flows': cash_flows,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'frequency': frequency
        }
    
    def _generate_dates(self, start_date, end_date, frequency: str) -> List[datetime.date]:
        """Genera lista de fechas según la frecuencia"""
        dates = []
        current = start_date
        
        if frequency == 'daily':
            delta = timedelta(days=1)
        elif frequency == 'weekly':
            delta = timedelta(days=7)
        elif frequency == 'monthly':
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=7)  # Default: weekly
        
        while current <= end_date:
            dates.append(current)
            current += delta
        
        # Asegurar que incluimos la fecha final
        if dates[-1] != end_date:
            dates.append(end_date)
        
        return dates
    
    def _get_capital_invested(self, date: datetime.date) -> float:
        """Calcula el capital invertido neto hasta una fecha"""
        deposits = db.session.query(func.sum(Transaction.amount))\
            .filter(
                Transaction.user_id == self.user_id,
                Transaction.transaction_type == 'DEPOSIT',
                Transaction.transaction_date <= datetime.combine(date, datetime.max.time())
            ).scalar() or 0
        
        withdrawals = db.session.query(func.sum(Transaction.amount))\
            .filter(
                Transaction.user_id == self.user_id,
                Transaction.transaction_type == 'WITHDRAWAL',
                Transaction.transaction_date <= datetime.combine(date, datetime.max.time())
            ).scalar() or 0
        
        return float(deposits - abs(withdrawals))
    
    def _get_cash_flows(self) -> List[Dict[str, Any]]:
        """Obtiene todos los deposits y withdrawals para marcadores"""
        cash_flows = Transaction.query.filter(
            Transaction.user_id == self.user_id,
            Transaction.transaction_type.in_(['DEPOSIT', 'WITHDRAWAL'])
        ).order_by(Transaction.transaction_date.asc()).all()
        
        return [{
            'date': cf.transaction_date.strftime('%Y-%m-%d'),
            'type': cf.transaction_type,
            'amount': float(cf.amount)
        } for cf in cash_flows]
    
    def _get_pl_accumulated_approx(self, date: datetime.date, portfolio_value: float, capital_invested: float) -> float:
        """
        Aproximación de P&L para fechas históricas.
        Fórmula simple: P&L ≈ Valor Portfolio - Capital Invertido + Dividendos - Comisiones
        """
        date_dt = datetime.combine(date, datetime.max.time())
        
        # Dividendos recibidos hasta la fecha
        dividends = db.session.query(func.sum(Transaction.amount))\
            .filter(
                Transaction.user_id == self.user_id,
                Transaction.transaction_type == 'DIVIDEND',
                Transaction.transaction_date <= date_dt
            ).scalar() or 0
        
        # Comisiones pagadas hasta la fecha
        fees = db.session.query(func.sum(Transaction.amount))\
            .filter(
                Transaction.user_id == self.user_id,
                Transaction.transaction_type.in_(['FEE', 'INTEREST', 'TAX']),
                Transaction.transaction_date <= date_dt
            ).scalar() or 0
        
        # P&L aproximado = Portfolio - Capital + Dividendos - Comisiones
        pl_approx = portfolio_value - capital_invested + dividends - abs(fees)
        
        return float(pl_approx)
    
    def _get_dividends_until(self, date: datetime.date) -> float:
        """Obtener dividendos acumulados hasta la fecha (convertidos a EUR)"""
        date_dt = datetime.combine(date, datetime.max.time())
        
        dividends = Transaction.query.filter(
            Transaction.user_id == self.user_id,
            Transaction.transaction_type == 'DIVIDEND',
            Transaction.transaction_date <= date_dt
        ).all()
        
        total_eur = sum(convert_to_eur(abs(txn.amount), txn.currency) for txn in dividends)
        return float(total_eur)
    
    def _get_fees_until(self, date: datetime.date) -> float:
        """Obtener comisiones acumuladas hasta la fecha (convertidas a EUR)"""
        date_dt = datetime.combine(date, datetime.max.time())
        
        fees = Transaction.query.filter(
            Transaction.user_id == self.user_id,
            Transaction.transaction_type.in_(['FEE', 'INTEREST', 'TAX']),
            Transaction.transaction_date <= date_dt
        ).all()
        
        total_eur = sum(convert_to_eur(abs(txn.amount), txn.currency) for txn in fees)
        return float(total_eur)
    
    def _get_pl_realized_until(self, date: datetime.date) -> float:
        """Calcular P&L Realizado histórico hasta la fecha usando FIFO"""
        from app.services.fifo_calculator import FIFOCalculator
        
        date_dt = datetime.combine(date, datetime.max.time())
        
        # Obtener transacciones hasta la fecha
        transactions = Transaction.query.filter(
            Transaction.user_id == self.user_id,
            Transaction.transaction_date <= date_dt,
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).order_by(Transaction.transaction_date).all()
        
        # Reconstruir FIFO por asset
        fifo_by_asset = {}
        total_pl_realized = 0.0
        
        for txn in transactions:
            if not txn.asset_id:
                continue
                
            asset_id = txn.asset_id
            
            # Crear FIFO si no existe
            if asset_id not in fifo_by_asset:
                symbol = txn.asset.symbol if txn.asset else f"Asset_{asset_id}"
                fifo_by_asset[asset_id] = FIFOCalculator(symbol=symbol)
            
            fifo = fifo_by_asset[asset_id]
            
            if txn.transaction_type == 'BUY':
                # Registrar compra
                total_cost = (txn.quantity * txn.price) + txn.commission + txn.fees + txn.tax
                fifo.add_buy(
                    quantity=txn.quantity,
                    price=txn.price,
                    date=txn.transaction_date,
                    total_cost=total_cost
                )
            
            elif txn.transaction_type == 'SELL':
                # Registrar venta y obtener coste base
                cost_basis = fifo.add_sell(
                    quantity=txn.quantity,
                    date=txn.transaction_date
                )
                
                # Calcular ganancia/pérdida de esta venta (convertir a float para compatibilidad)
                proceeds = float((txn.quantity * txn.price) - txn.commission - txn.fees - txn.tax)
                cost_basis_float = float(cost_basis)
                pl_this_sale = proceeds - cost_basis_float
                
                # Convertir a EUR
                pl_eur = convert_to_eur(pl_this_sale, txn.currency)
                total_pl_realized += pl_eur
        
        return float(total_pl_realized)
    
    def _empty_response(self) -> Dict[str, Any]:
        """Respuesta vacía cuando no hay datos"""
        return {
            'labels': [],
            'datasets': {
                'portfolio_value': [],
                'capital_invested': [],
                'returns_pct': []
            },
            'cash_flows': [],
            'start_date': None,
            'end_date': None,
            'frequency': 'weekly'
        }

