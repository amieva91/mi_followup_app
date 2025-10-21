"""
Excepciones personalizadas para Market Data Services
"""

class MarketDataException(Exception):
    """Excepción base para errores de market data"""
    pass


class EnrichmentException(MarketDataException):
    """Error al enriquecer un asset"""
    pass


class PriceUpdateException(MarketDataException):
    """Error al actualizar precio de un asset"""
    pass


class ProviderException(MarketDataException):
    """Error en un provider específico"""
    pass


class RateLimitException(ProviderException):
    """Rate limit alcanzado"""
    pass


class AssetNotFoundException(ProviderException):
    """Asset no encontrado en el provider"""
    pass

