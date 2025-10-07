"""
Modelos de Broker y BrokerAccount
"""
from datetime import datetime
from app import db


class Broker(db.Model):
    """Catálogo de brokers disponibles"""
    __tablename__ = 'brokers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'IBKR', 'DeGiro', 'Manual'
    full_name = db.Column(db.String(100))  # 'Interactive Brokers'
    is_active = db.Column(db.Boolean, default=True)
    
    # Relaciones
    accounts = db.relationship('BrokerAccount', backref='broker', lazy=True)
    
    def __repr__(self):
        return f"Broker('{self.name}', '{self.full_name}')"


class BrokerAccount(db.Model):
    """Cuentas de usuario en brokers"""
    __tablename__ = 'broker_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.id'), nullable=False)
    
    account_number = db.Column(db.String(50), nullable=True)  # 'U12722327'
    account_name = db.Column(db.String(100))  # Nombre descriptivo
    base_currency = db.Column(db.String(3), default='EUR')  # Divisa base
    
    # Control de margen/apalancamiento
    margin_enabled = db.Column(db.Boolean, default=False)
    current_cash = db.Column(db.Float, default=0.0)  # Efectivo disponible
    margin_used = db.Column(db.Float, default=0.0)  # Margen utilizado
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('broker_accounts', lazy=True))
    holdings = db.relationship('PortfolioHolding', backref='account', lazy=True)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    cash_flows = db.relationship('CashFlow', backref='account', lazy=True)
    metrics = db.relationship('PortfolioMetrics', backref='account', lazy=True)
    
    def __repr__(self):
        return f"BrokerAccount('{self.account_name}', '{self.broker.name if self.broker else 'N/A'}')"
    
    @property
    def leverage_ratio(self):
        """Calcula el ratio de apalancamiento"""
        if self.current_cash <= 0:
            return 0.0
        total_value = self.current_cash + self.margin_used
        return total_value / self.current_cash if self.current_cash > 0 else 0.0

