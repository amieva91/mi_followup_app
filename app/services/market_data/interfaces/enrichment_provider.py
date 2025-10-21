"""
Interface base para providers de enriquecimiento de assets
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict

class EnrichmentProvider(ABC):
    """
    Interface que deben implementar todos los providers de enriquecimiento
    Ejemplos: OpenFIGI, Alpha Vantage, Bloomberg, etc.
    """
    
    @abstractmethod
    def enrich_by_isin(self, isin: str, currency: Optional[str] = None) -> Optional[Dict]:
        """
        Enriquece un asset usando su ISIN
        
        Args:
            isin: Código ISIN del asset
            currency: Moneda opcional para filtrar resultados
            
        Returns:
            Dict con datos del asset o None si no se encuentra
            {
                'symbol': str,
                'name': str,
                'exchange': str,
                'mic': str,
                'currency': str,
                'asset_type': str,
                'composite_figi': str,
                ...
            }
        """
        pass
    
    @abstractmethod
    def enrich_by_symbol(self, symbol: str, exchange: Optional[str] = None) -> Optional[Dict]:
        """
        Enriquece un asset usando su símbolo
        
        Args:
            symbol: Símbolo del asset (ticker)
            exchange: Exchange opcional para filtrar resultados
            
        Returns:
            Dict con datos del asset o None si no se encuentra
        """
        pass

