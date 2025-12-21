"""
Mapeo de MIC ISO 10383 a sufijo de Yahoo Finance

NOTA: Todos los mapeos están en la base de datos (MappingRegistry).
Este módulo solo contiene métodos que leen desde BD.
"""
from app.models import MappingRegistry

class YahooSuffixMapper:
    """
    Mapea códigos MIC (Market Identifier Code) ISO 10383 a sufijos de Yahoo Finance
    
    Todos los mapeos se leen desde MappingRegistry (base de datos).
    No hay diccionarios hardcodeados en este módulo.
    """
    
    # Sufijos Yahoo Finance → nombre del mercado
    SUFFIX_NAMES = {
        '': 'United States',
        '.L': 'London',
        '.PA': 'Paris',
        '.DE': 'Germany (XETRA)',
        '.F': 'Frankfurt',
        '.MC': 'Madrid',
        '.MI': 'Milan',
        '.AS': 'Amsterdam',
        '.ST': 'Stockholm',
        '.HE': 'Helsinki',
        '.CO': 'Copenhagen',
        '.OL': 'Oslo',
        '.WA': 'Warsaw',
        '.PR': 'Prague',
        '.BD': 'Budapest',
        '.BR': 'Brussels',
        '.LS': 'Lisbon',
        '.VI': 'Vienna',
        '.SW': 'Switzerland',
        '.HK': 'Hong Kong',
        '.T': 'Tokyo',
        '.SS': 'Shanghai',
        '.SZ': 'Shenzhen',
        '.KS': 'Korea',
        '.TW': 'Taiwan',
        '.SI': 'Singapore',
        '.AX': 'Australia',
        '.NZ': 'New Zealand',
        '.TO': 'Toronto',
        '.V': 'TSX Venture',
        '.BO': 'Bombay',
        '.NS': 'India NSE',
        '.SA': 'Sao Paulo',
        '.MX': 'Mexico',
    }
    
    @classmethod
    def mic_to_yahoo_suffix(cls, mic: str) -> str:
        """
        Convierte un MIC ISO 10383 al sufijo de Yahoo Finance
        LEE DESDE BASE DE DATOS (MappingRegistry)
        
        Args:
            mic: Código MIC (ej: 'XMAD', 'XLON')
            
        Returns:
            Sufijo Yahoo (ej: '.MC', '.L')
        """
        if not mic:
            return ''
        
        # Leer desde BD (MappingRegistry)
        result = MappingRegistry.get_mapping('MIC_TO_YAHOO', mic)
        return result if result is not None else ''
    
    @classmethod
    def get_market_name(cls, suffix: str) -> str:
        """
        Obtiene el nombre del mercado a partir del sufijo
        
        Args:
            suffix: Sufijo Yahoo (ej: '.MC')
            
        Returns:
            Nombre del mercado (ej: 'Madrid')
        """
        return cls.SUFFIX_NAMES.get(suffix, 'Unknown')
    
    @classmethod
    def get_all_mics(cls):
        """Retorna todos los MICs soportados desde la base de datos"""
        mappings = MappingRegistry.query.filter_by(
            mapping_type='MIC_TO_YAHOO',
            is_active=True
        ).all()
        return [m.source_key for m in mappings]
    
    @classmethod
    def get_all_suffixes(cls):
        """Retorna todos los sufijos únicos soportados desde la base de datos"""
        mappings = MappingRegistry.query.filter_by(
            mapping_type='MIC_TO_YAHOO',
            is_active=True
        ).all()
        return list(set(m.target_value for m in mappings if m.target_value))
    
    @classmethod
    def exchange_to_yahoo_suffix(cls, exchange: str) -> str:
        """
        Mapea código de exchange (IBKR unificado) a sufijo de Yahoo Finance
        Fallback cuando no hay MIC disponible
        LEE DESDE BASE DE DATOS (MappingRegistry)
        
        Args:
            exchange: Código de exchange (ej: 'NASDAQ', 'BM', 'LSE')
            
        Returns:
            Sufijo de Yahoo Finance (ej: '', '.MC', '.L')
            None si el exchange no se encuentra en el mapeo
        """
        if not exchange:
            return None
        
        # Leer desde BD (MappingRegistry)
        return MappingRegistry.get_mapping('EXCHANGE_TO_YAHOO', exchange)

