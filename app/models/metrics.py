"""
Modelo de PortfolioMetrics (Métricas calculadas)
"""
from datetime import datetime
from app import db


class PortfolioMetrics(db.Model):
    """Métricas calculadas del portfolio (MTD/YTD)"""
    __tablename__ = 'portfolio_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'))  # Null = todas las cuentas
    
    # Período
    metric_date = db.Column(db.Date, nullable=False, index=True)
    metric_type = db.Column(db.String(20), nullable=False)  # 'DAILY', 'MONTHLY', 'YEARLY'
    
    # Valores del portfolio
    total_value = db.Column(db.Float, nullable=False)  # Valor total
    total_cost = db.Column(db.Float, nullable=False)  # Coste total invertido
    cash_balance = db.Column(db.Float, default=0.0)  # Efectivo disponible
    
    # P&L
    realized_pl = db.Column(db.Float, default=0.0)  # P&L realizadas acumuladas
    unrealized_pl = db.Column(db.Float, default=0.0)  # P&L no realizadas actuales
    total_pl = db.Column(db.Float, default=0.0)  # Total P&L
    
    # Retornos
    total_return_pct = db.Column(db.Float)  # Retorno total %
    mtd_return_pct = db.Column(db.Float)  # Retorno del mes %
    ytd_return_pct = db.Column(db.Float)  # Retorno del año %
    
    # Apalancamiento
    margin_used = db.Column(db.Float, default=0.0)
    leverage_ratio = db.Column(db.Float)  # Ratio de apalancamiento
    
    # Métricas de riesgo (para fase 3)
    sharpe_ratio = db.Column(db.Float)
    max_drawdown = db.Column(db.Float)
    volatility = db.Column(db.Float)
    
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('metrics', lazy=True))
    
    def __repr__(self):
        return f"PortfolioMetrics('{self.metric_date}', {self.total_value})"
    
    def calculate_returns(self):
        """Calcula los porcentajes de retorno"""
        if self.total_cost > 0:
            self.total_return_pct = (self.total_pl / self.total_cost) * 100
        else:
            self.total_return_pct = 0.0
    
    def calculate_leverage(self, cash_balance, margin_used):
        """Calcula el ratio de apalancamiento"""
        self.margin_used = margin_used
        if cash_balance > 0:
            total_exposure = cash_balance + margin_used
            self.leverage_ratio = total_exposure / cash_balance
        else:
            self.leverage_ratio = 0.0

