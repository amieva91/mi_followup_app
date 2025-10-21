"""
Market Data Services
Módulo aislado para enriquecimiento de assets y actualización de precios
Fácilmente reemplazable si cambiamos de proveedores en el futuro
"""
from .services.asset_enricher import AssetEnricher
from .services.price_updater import PriceUpdater

__all__ = ['AssetEnricher', 'PriceUpdater']

