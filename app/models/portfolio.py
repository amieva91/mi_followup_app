"""
Modelo de Portfolio (Holdings/Posiciones)
"""
from datetime import datetime
from app import db


class PortfolioHolding(db.Model):
    """Posiciones actuales en el portfolio"""
    __tablename__ = 'portfolio_holdings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    
    # Datos de la posición
    quantity = db.Column(db.Float, nullable=False)  # Cantidad actual
    average_buy_price = db.Column(db.Float, nullable=False)  # Precio medio de compra
    total_cost = db.Column(db.Float, nullable=False)  # Coste total (base de coste)
    
    # Información adicional
    first_purchase_date = db.Column(db.Date, nullable=False)
    last_transaction_date = db.Column(db.Date)
    
    # P&L Calculadas (actualizables)
    current_price = db.Column(db.Float)  # Precio actual de mercado
    current_value = db.Column(db.Float)  # Valor actual (quantity * current_price)
    unrealized_pl = db.Column(db.Float)  # P&L no realizadas (latentes)
    unrealized_pl_pct = db.Column(db.Float)  # % de retorno no realizado
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('holdings', lazy=True))
    
    # Constraint: Una sola posición por activo-cuenta
    __table_args__ = (
        db.UniqueConstraint('account_id', 'asset_id', name='unique_account_asset'),
    )
    
    def __repr__(self):
        return f"PortfolioHolding('{self.asset.symbol if self.asset else 'N/A'}', {self.quantity})"
    
    def update_market_value(self, current_price):
        """Actualiza el valor de mercado y P&L no realizadas"""
        self.current_price = current_price
        self.current_value = self.quantity * current_price
        self.unrealized_pl = self.current_value - self.total_cost
        if self.total_cost > 0:
            self.unrealized_pl_pct = (self.unrealized_pl / self.total_cost) * 100
        else:
            self.unrealized_pl_pct = 0.0
    
    def add_purchase(self, quantity, price, total_cost):
        """Añade una compra (actualiza precio medio)"""
        new_total_cost = self.total_cost + total_cost
        new_quantity = self.quantity + quantity
        
        if new_quantity > 0:
            self.average_buy_price = new_total_cost / new_quantity
            self.quantity = new_quantity
            self.total_cost = new_total_cost
    
    def subtract_sale(self, quantity, realized_pl):
        """Resta una venta (método FIFO)"""
        if quantity > self.quantity:
            raise ValueError("Cannot sell more than current quantity")
        
        # Calcular coste proporcional de las acciones vendidas
        cost_per_share = self.total_cost / self.quantity
        cost_sold = cost_per_share * quantity
        
        # Actualizar holding
        self.quantity -= quantity
        self.total_cost -= cost_sold
        
        # Si se vendió todo, resetear
        if self.quantity == 0:
            self.average_buy_price = 0.0
            self.total_cost = 0.0

