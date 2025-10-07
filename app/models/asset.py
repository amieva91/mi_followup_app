"""
Modelo de Asset (Activos financieros)
"""
from datetime import datetime
from app import db


class Asset(db.Model):
    """Catálogo de activos financieros"""
    __tablename__ = 'assets'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Identificadores
    symbol = db.Column(db.String(20), nullable=False, index=True)  # 'AAPL', '9997'
    isin = db.Column(db.String(12), unique=True, nullable=True, index=True)  # 'US0378331005'
    name = db.Column(db.String(200), nullable=False)  # 'Apple Inc.'
    
    # Clasificación
    asset_type = db.Column(db.String(20), nullable=False)  # 'Stock', 'ETF', 'Bond', 'Crypto'
    sector = db.Column(db.String(50))  # 'Technology', 'Finance'
    exchange = db.Column(db.String(10))  # 'NASDAQ', 'HKG', 'WSE'
    currency = db.Column(db.String(3), nullable=False)  # 'USD', 'EUR', 'HKD'
    
    # Para actualización de precios
    yahoo_symbol = db.Column(db.String(20))  # Símbolo para Yahoo Finance API
    last_price = db.Column(db.Float)  # Último precio conocido
    last_price_update = db.Column(db.DateTime)  # Última actualización
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    holdings = db.relationship('PortfolioHolding', backref='asset', lazy=True)
    transactions = db.relationship('Transaction', backref='asset', lazy=True)
    price_history = db.relationship('PriceHistory', backref='asset', lazy=True)
    
    def __repr__(self):
        return f"Asset('{self.symbol}', '{self.name}')"
    
    def update_price(self, new_price):
        """Actualiza el precio del activo"""
        self.last_price = new_price
        self.last_price_update = datetime.utcnow()


class PriceHistory(db.Model):
    """Histórico de precios de activos"""
    __tablename__ = 'price_history'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    
    date = db.Column(db.Date, nullable=False, index=True)
    open_price = db.Column(db.Float)
    high_price = db.Column(db.Float)
    low_price = db.Column(db.Float)
    close_price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.BigInteger)
    
    source = db.Column(db.String(20), default='YAHOO')  # 'YAHOO', 'MANUAL'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Constraint: Un precio por día por activo
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'date', name='unique_asset_date'),
    )
    
    def __repr__(self):
        return f"PriceHistory('{self.asset.symbol if self.asset else 'N/A'}', '{self.date}', {self.close_price})"

