"""
Mapeo de códigos de exchange entre diferentes formatos
DeGiro col4 → IBKR exchange → Yahoo Finance suffix
"""

class ExchangeMapper:
    """
    Centraliza el mapeo de exchanges entre diferentes proveedores
    """
    
    # DeGiro columna 4 "Bolsa de" → código unificado IBKR-style
    DEGIRO_TO_UNIFIED = {
        # US markets
        'ASE': 'NASDAQ',  # American Stock Exchange (ahora parte de NYSE)
        'NDQ': 'NASDAQ',
        'NSY': 'NYSE',
        
        # European markets
        'LSE': 'LSE',      # London
        'EPA': 'SBF',      # Euronext Paris
        'FRA': 'IBIS',     # Frankfurt
        'XET': 'IBIS',     # XETRA (Frankfurt electronic)
        'EAM': 'AEB',      # Amsterdam
        'MAD': 'BM',       # Madrid (Bolsa de Madrid)
        'MIL': 'BVME',     # Milan (Borsa Italiana)
        'OMX': 'SFB',      # Stockholm (OMX Nordic)
        'OSL': 'OSE',      # Oslo
        'WSE': 'WSE',      # Warsaw
        
        # Asian/Pacific markets
        'HKS': 'SEHK',     # Hong Kong
        'ASX': 'ASX',      # Australian
        'TOR': 'TSE',      # Toronto
        'TSV': 'TSXV',     # TSX Venture
        
        # Other
        'OMK': 'CPH',      # Copenhagen (OMX)
        'TDG': 'TRADEGATE', # Tradegate (Germany)
    }
    
    # Exchange unificado → nombre completo
    EXCHANGE_NAMES = {
        'NASDAQ': 'NASDAQ',
        'NYSE': 'New York Stock Exchange',
        'LSE': 'London Stock Exchange',
        'SBF': 'Euronext Paris',
        'IBIS': 'XETRA (Frankfurt)',
        'AEB': 'Euronext Amsterdam',
        'BM': 'Bolsa de Madrid',
        'BVME': 'Borsa Italiana',
        'SFB': 'Nasdaq Stockholm',
        'OSE': 'Oslo Stock Exchange',
        'WSE': 'Warsaw Stock Exchange',
        'SEHK': 'Hong Kong Stock Exchange',
        'ASX': 'Australian Securities Exchange',
        'TSE': 'Toronto Stock Exchange',
        'TSXV': 'TSX Venture Exchange',
        'CPH': 'Nasdaq Copenhagen',
        'TRADEGATE': 'Tradegate Exchange',
    }
    
    @classmethod
    def degiro_to_unified(cls, degiro_code: str) -> str:
        """
        Convierte código DeGiro (columna 4) a formato unificado
        LEE DESDE BASE DE DATOS (MappingRegistry)
        
        Args:
            degiro_code: Código de "Bolsa de" (ej: 'NDQ', 'MAD')
            
        Returns:
            Código unificado (ej: 'NASDAQ', 'BM')
        """
        if not degiro_code:
            return degiro_code
        
        # Leer desde BD (MappingRegistry)
        from app.models import MappingRegistry
        result = MappingRegistry.get_mapping('DEGIRO_TO_IBKR', degiro_code)
        return result if result is not None else degiro_code
    
    @classmethod
    def get_exchange_name(cls, exchange_code: str) -> str:
        """
        Obtiene el nombre completo del exchange
        
        Args:
            exchange_code: Código del exchange (ej: 'NASDAQ')
            
        Returns:
            Nombre completo (ej: 'NASDAQ')
        """
        return cls.EXCHANGE_NAMES.get(exchange_code, exchange_code)

