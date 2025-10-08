"""
Modelos de Transaction y CashFlow
"""
from datetime import datetime
from app import db


class Transaction(db.Model):
    """Todas las transacciones del portfolio"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)  # Null para cash ops
    
    # Información básica
    transaction_type = db.Column(db.String(20), nullable=False, index=True)
    # Tipos: 'BUY', 'SELL', 'DIVIDEND', 'FEE', 'INTEREST', 'TAX', 'DEPOSIT', 'WITHDRAWAL'
    
    transaction_date = db.Column(db.DateTime, nullable=False, index=True)
    settlement_date = db.Column(db.Date)  # Fecha valor
    
    # Detalles financieros
    quantity = db.Column(db.Float)  # Para compra/venta (null para dividendos/comisiones)
    price = db.Column(db.Float)  # Precio por unidad
    amount = db.Column(db.Float, nullable=False)  # Monto total (+ ingreso, - gasto)
    currency = db.Column(db.String(3), nullable=False)
    
    # Montos originales (para dividendos con conversión FX)
    amount_original = db.Column(db.Float)  # Monto en divisa original antes de conversión
    currency_original = db.Column(db.String(3))  # Divisa original antes de conversión
    
    # Costes asociados
    commission = db.Column(db.Float, default=0.0)  # Comisión
    fees = db.Column(db.Float, default=0.0)  # Otros gastos
    tax = db.Column(db.Float, default=0.0)  # Impuestos/retenciones en divisa original
    tax_eur = db.Column(db.Float, default=0.0)  # Impuestos/retenciones en EUR (para conversión)
    
    # P&L (para ventas)
    realized_pl = db.Column(db.Float)  # P&L realizada en esta transacción
    realized_pl_pct = db.Column(db.Float)  # % de retorno realizado
    
    # Identificadores externos
    external_id = db.Column(db.String(100))  # ID de orden del broker
    
    # Metadata
    description = db.Column(db.String(500))  # Descripción de la transacción
    notes = db.Column(db.Text)  # Notas del usuario
    source = db.Column(db.String(20), default='MANUAL')  # 'CSV_IBKR', 'CSV_DEGIRO', 'MANUAL'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
    
    def __repr__(self):
        asset_str = self.asset.symbol if self.asset else 'CASH'
        return f"Transaction('{self.transaction_type}', '{asset_str}', {self.amount})"
    
    @property
    def total_cost(self):
        """Coste total incluyendo comisiones y fees"""
        return abs(self.amount) + self.commission + self.fees + self.tax


class CashFlow(db.Model):
    """Depósitos y retiradas de efectivo"""
    __tablename__ = 'cash_flows'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    
    flow_type = db.Column(db.String(20), nullable=False)  # 'DEPOSIT', 'WITHDRAWAL'
    amount = db.Column(db.Float, nullable=False)  # + para depósito, - para retirada
    currency = db.Column(db.String(3), nullable=False)
    
    flow_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('cash_flows', lazy=True))
    
    def __repr__(self):
        return f"CashFlow('{self.flow_type}', {self.amount}, '{self.flow_date}')"

