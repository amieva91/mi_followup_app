"""
Modelo de Watchlist (Lista de seguimiento de assets)
"""
from datetime import datetime, date
from app import db


class Watchlist(db.Model):
    """
    Watchlist - Relación many-to-many User-Asset con métricas personalizadas
    """
    __tablename__ = 'watchlist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    
    # Campos manuales (input del usuario)
    next_earnings_date = db.Column(db.Date)  # Fecha próximos resultados
    per_ntm = db.Column(db.Float)  # PER o NTM P/E
    ntm_dividend_yield = db.Column(db.Float)  # NTM Dividend Yield (%)
    eps = db.Column(db.Float)  # Earnings Per Share
    cagr_revenue_yoy = db.Column(db.Float)  # CAGR Revenue YoY (%)
    
    # Campos calculados/caché (se actualizan automáticamente)
    operativa_indicator = db.Column(db.String(10))  # BUY, SELL, HOLD, o "-" (default)
    tier = db.Column(db.Integer)  # Tier 1-5 (calculado)
    cantidad_aumentar_reducir = db.Column(db.Float)  # Diferencia vs Tier (EUR)
    rentabilidad_5yr = db.Column(db.Float)  # Rentabilidad a 5 años (%)
    rentabilidad_anual = db.Column(db.Float)  # Rentabilidad Anual (%)
    valoracion_12m = db.Column(db.Float)  # Valoración actual 12 meses (%)
    target_price_5yr = db.Column(db.Float)  # Target Price (5 yr)
    precio_actual = db.Column(db.Float)  # Precio actual (caché)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('watchlist_items', lazy=True))
    asset = db.relationship('Asset', backref=db.backref('watchlist_items', lazy=True))
    
    # Constraint: Un usuario no puede tener el mismo asset dos veces en watchlist
    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', name='unique_user_asset_watchlist'),
    )
    
    def __repr__(self):
        return f"Watchlist(user_id={self.user_id}, asset_id={self.asset_id})"


class WatchlistConfig(db.Model):
    """
    Configuración de watchlist por usuario (umbrales y Tier)
    """
    __tablename__ = 'watchlist_config'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # Umbral máximo peso en cartera (por defecto 10%)
    max_weight_threshold = db.Column(db.Float, default=10.0, nullable=False)
    
    # Rangos de Tier (JSON): qué rangos de Valoración actual 12 meses (%) corresponden a cada Tier
    # Ejemplo: {"tier_5": {"min": 50.0}, "tier_4": {"min": 30.0, "max": 50.0}, ...}
    tier_ranges = db.Column(db.Text)  # JSON string
    
    # Cantidades absolutas por Tier (JSON): cantidades en EUR para cada Tier
    # Ejemplo: {"tier_1": 500.0, "tier_2": 1000.0, "tier_3": 2000.0, "tier_4": 5000.0, "tier_5": 10000.0}
    tier_amounts = db.Column(db.Text)  # JSON string
    
    # Umbrales de colores para valores calculados (JSON)
    # Ejemplo: {
    #   "valoracion_12m": {"green_min": 10.0, "yellow_min": 0.0, "yellow_max": 10.0},
    #   "peso_cartera": {"green_max": 11.0, "yellow_min": 11.0, "yellow_max": 12.5},
    #   "fecha_resultados": {"yellow_days": 15},
    #   "precio_actual": {"green_pct": 10.0, "yellow_pct": 20.0}
    # }
    color_thresholds = db.Column(db.Text)  # JSON string
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('watchlist_config', uselist=False))
    
    def __repr__(self):
        return f"WatchlistConfig(user_id={self.user_id}, max_weight={self.max_weight_threshold})"
    
    def get_tier_ranges_dict(self):
        """Obtener tier_ranges como diccionario"""
        import json
        if self.tier_ranges:
            return json.loads(self.tier_ranges)
        return self._default_tier_ranges()
    
    def set_tier_ranges_dict(self, data):
        """Guardar tier_ranges como JSON string"""
        import json
        self.tier_ranges = json.dumps(data)
    
    def get_tier_amounts_dict(self):
        """Obtener tier_amounts como diccionario"""
        import json
        if self.tier_amounts:
            return json.loads(self.tier_amounts)
        return self._default_tier_amounts()
    
    def set_tier_amounts_dict(self, data):
        """Guardar tier_amounts como JSON string"""
        import json
        self.tier_amounts = json.dumps(data)
    
    def get_color_thresholds_dict(self):
        """Obtener color_thresholds como diccionario"""
        import json
        if self.color_thresholds:
            return json.loads(self.color_thresholds)
        return self._default_color_thresholds()
    
    def set_color_thresholds_dict(self, data):
        """Guardar color_thresholds como JSON string"""
        import json
        self.color_thresholds = json.dumps(data)
    
    @staticmethod
    def _default_color_thresholds():
        """Umbrales por defecto para colores"""
        return {
            "valoracion_12m": {
                "green_min": 10.0,  # Verde si >= green_min% (después de invertir signo: infravalorado = positivo = verde)
                "yellow_min": 0.0,  # Amarillo si >= yellow_min% y < green_min%
                # Rojo si < yellow_min% (después de invertir signo: sobrevalorado = negativo = rojo)
            },
            "peso_cartera": {
                "green_max_pct": 10.0,  # Verde si < umbral + 10%
                "yellow_min_pct": 10.0,  # Amarillo si umbral+10% <= x < umbral+25%
                "yellow_max_pct": 25.0,
                "red_min_pct": 25.0  # Rojo si >= umbral + 25%
            },
            "fecha_resultados": {
                "yellow_days": 15  # Amarillo si pasó <= 15 días
            },
            "tier": {
                "green_pct": 25.0,  # Verde si dentro ±25%
                "yellow_pct": 50.0  # Amarillo si dentro ±50%
            },
            "rentabilidad_5yr": {
                "green_min": 60.0,  # Verde si >= 60%
                "yellow_min": 30.0  # Amarillo si >= 30% y < 60%, Rojo si < 30%
            },
            "rentabilidad_anual": {
                "green_min": 10.0,  # Verde si >= 10%
                "yellow_min": 0.0   # Amarillo si >= 0% y < 10%, Rojo si < 0%
            }
        }
    
    @staticmethod
    def _default_tier_ranges():
        """
        Rangos por defecto para Tier según Valoración actual 12 meses (%)
        
        Los rangos se construyen automáticamente desde valores simples:
        - Tier 5: >= 50%
        - Tier 4: >= 30% y < 50% (max viene del Tier 5)
        - Tier 3: >= 10% y < 30% (max viene del Tier 4)
        - Tier 2: >= 0% y < 10% (max viene del Tier 3)
        - Tier 1: < 0% (max viene del Tier 2)
        """
        return {
            "tier_5": {"min": 50.0},  # >= 50%
            "tier_4": {"min": 30.0, "max": 50.0},  # 30% - 50%
            "tier_3": {"min": 10.0, "max": 30.0},  # 10% - 30%
            "tier_2": {"min": 0.0, "max": 10.0},  # 0% - 10%
            "tier_1": {"max": 0.0}  # < 0%
        }
    
    @staticmethod
    def _default_tier_amounts():
        """Cantidades por defecto para cada Tier (EUR)"""
        return {
            "tier_1": 500.0,
            "tier_2": 1000.0,
            "tier_3": 2000.0,
            "tier_4": 5000.0,
            "tier_5": 10000.0
        }

