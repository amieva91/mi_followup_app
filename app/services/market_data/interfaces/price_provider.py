"""
Interface base para providers de precios
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
from datetime import datetime

class PriceProvider(ABC):
    """
    Interface que deben implementar todos los providers de precios
    Ejemplos: Yahoo Finance, Alpha Vantage, IEX Cloud, etc.
    """
    
    @abstractmethod
    def get_current_price(self, symbol: str, suffix: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene el precio actual de un asset
        
        Args:
            symbol: Símbolo del asset (ticker)
            suffix: Sufijo opcional (ej: '.MC' para Yahoo Finance)
            
        Returns:
            Dict con datos del precio o None si no se encuentra
            {
                'price': float,
                'currency': str,
                'timestamp': datetime,
                'open': float,
                'high': float,
                'low': float,
                'volume': int,
                'change': float,
                'change_percent': float,
                ...
            }
        """
        pass
    
    @abstractmethod
    def parse_yahoo_url(self, url: str) -> Optional[Dict]:
        """
        Parsea una URL de Yahoo Finance para extraer symbol y suffix
        
        Args:
            url: URL de Yahoo Finance (ej: https://es.finance.yahoo.com/quote/PSG.MC/)
            
        Returns:
            Dict con symbol y suffix o None si no es válida
            {
                'symbol': str,
                'suffix': str,
                'full_ticker': str
            }
        """
        pass

