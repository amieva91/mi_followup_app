"""
Watchlist Price Update Service - Actualización de precios para assets en watchlist
"""
from typing import Dict, List, Optional
from app import db
from app.models import Watchlist, Asset
from app.services.market_data.services.price_updater import PriceUpdater
import logging

logger = logging.getLogger(__name__)


class WatchlistPriceUpdateService:
    """
    Servicio para actualizar precios de assets en watchlist
    Reutiliza PriceUpdater para obtener datos de Yahoo Finance
    """
    
    @staticmethod
    def update_prices_batch(user_id: int) -> Dict:
        """
        Actualiza precios y datos de Yahoo Finance para todos los assets en watchlist del usuario
        
        Args:
            user_id: ID del usuario
        
        Returns:
            Dict con estadísticas de la actualización:
            {
                'total': int,
                'success': int,
                'failed': int,
                'updated_watchlist_items': int,
                'errors': List[str]
            }
        """
        # Obtener todos los items de watchlist del usuario
        watchlist_items = Watchlist.query.filter_by(user_id=user_id).all()
        
        if not watchlist_items:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'updated_watchlist_items': 0,
                'errors': []
            }
        
        # Obtener asset_ids únicos
        asset_ids = list(set([item.asset_id for item in watchlist_items]))
        
        # Crear diccionario asset_id -> watchlist_items para actualizar después
        asset_to_watchlist_items = {}
        for item in watchlist_items:
            if item.asset_id not in asset_to_watchlist_items:
                asset_to_watchlist_items[item.asset_id] = []
            asset_to_watchlist_items[item.asset_id].append(item)
        
        logger.info(f"🔄 Actualizando precios para {len(asset_ids)} assets en watchlist del usuario {user_id}")
        
        # Usar PriceUpdater para actualizar precios de los assets
        price_updater = PriceUpdater()
        update_result = price_updater.update_asset_prices(asset_ids=asset_ids)
        
        # Actualizar precio_actual en los items de watchlist
        updated_count = 0
        for asset_id in asset_ids:
            asset = Asset.query.get(asset_id)
            if asset and asset.current_price is not None:
                # Actualizar precio_actual en todos los items de watchlist de este asset
                if asset_id in asset_to_watchlist_items:
                    for watchlist_item in asset_to_watchlist_items[asset_id]:
                        watchlist_item.precio_actual = asset.current_price
                        updated_count += 1
        
        # Guardar cambios en watchlist
        if updated_count > 0:
            db.session.commit()
        
        result = {
            'total': update_result.get('total', 0),
            'success': update_result.get('success', 0),
            'failed': update_result.get('failed', 0),
            'updated_watchlist_items': updated_count,
            'errors': update_result.get('errors', [])
        }
        
        logger.info(f"✅ Actualización completada: {updated_count} items de watchlist actualizados")
        
        return result

