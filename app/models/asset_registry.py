"""
Registro Global de Assets - Cache compartida entre todos los usuarios
Tabla maestra con mapeo ISIN → Symbol, Exchange, MIC, Yahoo Suffix
"""
from datetime import datetime
from app import db


class AssetRegistry(db.Model):
    """
    Tabla global de assets - Compartida entre todos los usuarios
    Se alimenta automáticamente al importar CSVs y con correcciones manuales
    """
    __tablename__ = 'asset_registry'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Identificadores únicos
    isin = db.Column(db.String(12), unique=True, nullable=False, index=True)  # US0378331005
    
    # Información del mercado
    mic = db.Column(db.String(4), index=True)  # XMAD, XNAS, XLON
    degiro_exchange = db.Column(db.String(10))  # MAD, NDQ, LSE (DeGiro col 4)
    ibkr_exchange = db.Column(db.String(10))  # BM, NASDAQ, LSE (IBKR unificado)
    
    # Yahoo Finance
    symbol = db.Column(db.String(20), index=True)  # AAPL, GRF, 0700
    yahoo_suffix = db.Column(db.String(5))  # .MC, .L, .HK, '' (vacío para US)
    
    # Información adicional
    name = db.Column(db.String(200))  # Apple Inc., Grifols SA
    asset_type = db.Column(db.String(20))  # Stock, ETF
    country = db.Column(db.String(50))  # 'United States', 'Spain', 'United Kingdom'
    currency = db.Column(db.String(3), nullable=False)  # USD, EUR, GBP
    
    # Metadata de enriquecimiento
    is_enriched = db.Column(db.Boolean, default=False, index=True)  # ¿Tiene symbol?
    enrichment_source = db.Column(db.String(20))  # 'OPENFIGI', 'YAHOO_URL', 'MANUAL'
    enrichment_date = db.Column(db.DateTime)  # Cuándo se enriqueció
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Contador de uso (para estadísticas)
    usage_count = db.Column(db.Integer, default=1)  # Cuántos usuarios lo usan
    
    @property
    def yahoo_ticker(self):
        """Construye el ticker completo para Yahoo Finance"""
        if not self.symbol:
            return None
        suffix = self.yahoo_suffix or ''
        return f"{self.symbol}{suffix}"
    
    @property
    def needs_enrichment(self):
        """
        Indica si necesita ser enriquecido con OpenFIGI
        
        Condición principal: debe tener al menos un symbol
        El MIC es opcional (mejora la precisión pero no es obligatorio)
        """
        return not self.symbol
    
    def mark_as_enriched(self, source: str):
        """Marca el asset como enriquecido"""
        self.is_enriched = True
        self.enrichment_source = source
        self.enrichment_date = datetime.utcnow()
    
    def __repr__(self):
        return f"AssetRegistry('{self.isin}', '{self.symbol or 'NO_SYMBOL'}', '{self.name}')"

