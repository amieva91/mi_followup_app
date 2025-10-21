"""
Servicio de actualización de precios
Actualiza precios para assets con holdings activos usando Yahoo Finance
"""
from typing import List, Dict, Optional
from datetime import datetime
from ..providers.yahoo_finance import YahooFinanceProvider
from ..exceptions import ProviderException

class PriceUpdater:
    """
    Servicio para actualizar precios de assets con holdings activos
    Usa Yahoo Finance como proveedor principal
    """
    
    def __init__(self, yahoo_provider: Optional[YahooFinanceProvider] = None):
        """
        Args:
            yahoo_provider: Proveedor de Yahoo Finance (opcional, se crea uno si no se proporciona)
        """
        self.yahoo = yahoo_provider or YahooFinanceProvider()
        self.stats = {
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
    
    def update_prices_for_active_holdings(self, user_id: Optional[int] = None) -> Dict:
        """
        Actualiza precios solo para assets que tienen holdings > 0
        
        Args:
            user_id: ID de usuario para filtrar holdings (opcional, si None actualiza todos)
        
        Returns:
            Dict con estadísticas de actualización:
            {
                'updated': int,
                'failed': int,
                'skipped': int,
                'errors': List[str]
            }
        """
        # Importar aquí para evitar dependencia circular
        from app import db
        from app.models import Asset, PortfolioHolding
        from sqlalchemy import func
        
        # Reset stats
        self.stats = {
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # Buscar assets con holdings > 0
        query = db.session.query(
            Asset,
            func.sum(PortfolioHolding.quantity).label('total_quantity')
        ).join(
            PortfolioHolding, Asset.id == PortfolioHolding.asset_id
        )
        
        if user_id:
            query = query.filter(PortfolioHolding.user_id == user_id)
        
        query = query.group_by(Asset.id).having(func.sum(PortfolioHolding.quantity) > 0)
        
        assets_with_holdings = query.all()
        
        print(f"\n🔄 Actualizando precios para {len(assets_with_holdings)} assets con holdings activos...")
        
        for asset, quantity in assets_with_holdings:
            self._update_asset_price(asset)
        
        # Commit all changes
        db.session.commit()
        
        print(f"\n✅ Actualización completada:")
        print(f"   ✓ Actualizados: {self.stats['updated']}")
        print(f"   ✗ Fallidos: {self.stats['failed']}")
        print(f"   ⊘ Omitidos: {self.stats['skipped']}")
        
        return self.stats
    
    def _update_asset_price(self, asset) -> bool:
        """
        Actualiza el precio de un asset individual
        
        Args:
            asset: Instancia de Asset
            
        Returns:
            True si se actualizó correctamente, False si falló
        """
        # Verificar que tenga yahoo_ticker
        if not asset.yahoo_ticker:
            self.stats['skipped'] += 1
            error_msg = f"{asset.name}: Sin yahoo_ticker (symbol: {asset.symbol}, suffix: {asset.yahoo_suffix})"
            self.stats['errors'].append(error_msg)
            print(f"   ⊘ {error_msg}")
            return False
        
        try:
            # Obtener precio actual
            price_data = self.yahoo.get_current_price(asset.yahoo_ticker)
            
            if not price_data or 'price' not in price_data:
                self.stats['failed'] += 1
                error_msg = f"{asset.name} ({asset.yahoo_ticker}): No se pudo obtener precio"
                self.stats['errors'].append(error_msg)
                print(f"   ✗ {error_msg}")
                return False
            
            # Actualizar asset
            asset.last_price = price_data['price']
            asset.last_price_update = datetime.utcnow()
            
            self.stats['updated'] += 1
            print(f"   ✓ {asset.name} ({asset.yahoo_ticker}): {price_data['price']} {asset.currency}")
            return True
        
        except Exception as e:
            self.stats['failed'] += 1
            error_msg = f"{asset.name} ({asset.yahoo_ticker}): {str(e)[:60]}"
            self.stats['errors'].append(error_msg)
            print(f"   ✗ {error_msg}")
            return False
    
    def update_single_asset(self, asset) -> bool:
        """
        Actualiza el precio de un solo asset
        
        Args:
            asset: Instancia de Asset
            
        Returns:
            True si se actualizó correctamente, False si falló
        """
        from app import db
        
        result = self._update_asset_price(asset)
        db.session.commit()
        return result

