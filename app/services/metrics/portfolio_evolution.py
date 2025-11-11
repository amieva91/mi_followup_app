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
        
        for date in dates:
            # Valor del portfolio (usar método estático)
            date_datetime = datetime.combine(date, datetime.max.time())
            value = PortfolioValuation.get_value_at_date(
                user_id=self.user_id,
                target_date=date_datetime,
                use_current_prices=(date == end_date)
            )
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
        
        # Obtener cash flows para marcadores
        cash_flows = self._get_cash_flows()
        
        return {
            'labels': [d.strftime('%Y-%m-%d') for d in dates],
            'datasets': {
                'portfolio_value': portfolio_values,
                'capital_invested': capital_invested,
                'returns_pct': returns_pct
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

