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
    symbol = db.Column(db.String(20), nullable=True, index=True)  # 'AAPL', '9997' - Nullable para DeGiro
    isin = db.Column(db.String(12), unique=True, nullable=True, index=True)  # 'US0378331005'
    name = db.Column(db.String(200), nullable=False)  # 'Apple Inc.'
    
    # Clasificación
    asset_type = db.Column(db.String(20), nullable=False)  # 'Stock', 'ETF', 'Bond', 'Crypto'
    sector = db.Column(db.String(50))  # 'Technology', 'Finance'
    country = db.Column(db.String(50))  # 'United States', 'Spain', 'United Kingdom'
    exchange = db.Column(db.String(10))  # 'NASDAQ', 'HKG', 'WSE' (formato unificado IBKR)
    currency = db.Column(db.String(3), nullable=False)  # 'USD', 'EUR', 'HKD'
    
    # Market Identifiers
    mic = db.Column(db.String(4))  # MIC ISO 10383 (ej: 'XMAD', 'XNAS') - Columna 5 DeGiro
    yahoo_suffix = db.Column(db.String(5))  # Sufijo Yahoo Finance (ej: '.MC', '.L', '')
    
    # ===== YAHOO FINANCE FIELDS (Sprint 3 Final) =====
    # PRECIOS Y CAMBIOS
    current_price = db.Column(db.Float)  # Precio actual
    previous_close = db.Column(db.Float)  # Cierre anterior
    day_change_percent = db.Column(db.Float)  # Cambio del día en %
    last_price_update = db.Column(db.DateTime)  # Última actualización de precios
    
    # VALORACIÓN
    market_cap = db.Column(db.Float)  # Capitalización de mercado (moneda original)
    market_cap_formatted = db.Column(db.String(20))  # "1.5B", "234M"
    market_cap_eur = db.Column(db.Float)  # Capitalización en EUR
    trailing_pe = db.Column(db.Float)  # P/E Ratio (trailing)
    forward_pe = db.Column(db.Float)  # P/E Ratio (forward)
    
    # INFORMACIÓN CORPORATIVA (sector ya existe arriba)
    industry = db.Column(db.String(100))  # 'Consumer Electronics', 'Banking'
    
    # RIESGO Y RENDIMIENTO
    beta = db.Column(db.Float)  # Beta (volatilidad vs mercado)
    dividend_rate = db.Column(db.Float)  # Dividendo anual
    dividend_yield = db.Column(db.Float)  # Rentabilidad por dividendo (%)
    
    # ANÁLISIS DE MERCADO
    recommendation_key = db.Column(db.String(20))  # 'buy', 'hold', 'sell', 'strong_buy'
    number_of_analyst_opinions = db.Column(db.Integer)  # Número de analistas
    target_mean_price = db.Column(db.Float)  # Precio objetivo medio
    
    # DEPRECATED FIELDS
    yahoo_symbol = db.Column(db.String(20))  # DEPRECATED: Usar yahoo_ticker property
    last_price = db.Column(db.Float)  # DEPRECATED: Usar current_price
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    holdings = db.relationship('PortfolioHolding', backref='asset', lazy=True)
    transactions = db.relationship('Transaction', backref='asset', lazy=True)
    price_history = db.relationship('PriceHistory', backref='asset', lazy=True)
    
    def __repr__(self):
        return f"Asset('{self.symbol}', '{self.name}')"
    
    @property
    def yahoo_ticker(self):
        """Construye el ticker completo para Yahoo Finance"""
        if not self.symbol:
            return None
        suffix = self.yahoo_suffix or ''
        return f"{self.symbol}{suffix}"
    
    def update_price(self, new_price):
        """Actualiza el precio del activo (mantener por compatibilidad)"""
        self.current_price = new_price
        self.last_price = new_price  # DEPRECATED: mantener por compatibilidad
        self.last_price_update = datetime.utcnow()
    
    @property
    def price_change_direction(self):
        """Retorna 'up', 'down' o 'neutral' para indicadores visuales"""
        if not self.day_change_percent:
            return 'neutral'
        return 'up' if self.day_change_percent > 0 else 'down' if self.day_change_percent < 0 else 'neutral'
    
    @property
    def is_price_stale(self):
        """Detecta si el precio está desactualizado o nunca se actualizó"""
        from datetime import timedelta
        if not self.current_price:
            return False  # No hay precio, no es "stale", simplemente no existe
        
        if not self.last_price_update:
            return True  # Hay precio pero sin fecha de actualización -> es antiguo
        
        # Precio antiguo si han pasado más de 7 días desde la última actualización
        age_threshold = timedelta(days=7)
        return (datetime.utcnow() - self.last_price_update) > age_threshold


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

