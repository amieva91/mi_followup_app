"""
PriceUpdater Service - Actualización de precios y métricas desde Yahoo Finance
Sprint 3 Final - Real-time Prices
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import time
import yfinance as yf
from app import db
from app.models.asset import Asset
from app.services.market_data.exceptions import PriceUpdateException


class PriceUpdater:
    """
    Servicio para actualizar precios y métricas de activos desde Yahoo Finance.
    """
    
    # Tasas de conversión hardcoded (simplificado para MVP)
    # TODO: En el futuro, obtener tasas dinámicas de una API de divisas
    EXCHANGE_RATES_TO_EUR = {
        'EUR': 1.0,
        'USD': 0.92,  # Aproximado
        'GBP': 1.17,
        'JPY': 0.0062,
        'CHF': 1.06,
        'AUD': 0.60,
        'CAD': 0.67,
        'HKD': 0.12,
        'SGD': 0.68,
        'NOK': 0.086,
        'SEK': 0.085,
        'DKK': 0.13,
    }
    
    def __init__(self):
        """Inicializar el servicio de actualización de precios."""
        self.errors = []
        self.warnings = []
    
    def update_asset_prices(self, asset_ids: Optional[List[int]] = None) -> Dict:
        """
        Actualiza precios de uno o varios activos.
        
        Args:
            asset_ids: Lista de IDs de activos. Si None, actualiza todos los activos con holdings > 0.
        
        Returns:
            Dict con estadísticas de la actualización
        """
        self.errors = []
        self.warnings = []
        
        # Obtener activos a actualizar
        if asset_ids:
            assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
        else:
            # Actualizar solo activos con posiciones actuales
            from app.models.portfolio import PortfolioHolding
            asset_ids_with_holdings = db.session.query(PortfolioHolding.asset_id).filter(
                PortfolioHolding.quantity > 0
            ).distinct().all()
            asset_ids_with_holdings = [a[0] for a in asset_ids_with_holdings]
            assets = Asset.query.filter(Asset.id.in_(asset_ids_with_holdings)).all()
        
        if not assets:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [],
                'warnings': []
            }
        
        total = len(assets)
        success = 0
        failed = 0
        skipped = 0
        
        for idx, asset in enumerate(assets):
            try:
                # Verificar que tenga ticker válido
                if not asset.yahoo_ticker:
                    skipped += 1
                    self.warnings.append(f"❌ {asset.symbol or asset.name}: Sin ticker de Yahoo Finance")
                    continue
                
                # Obtener datos de Yahoo Finance
                success_update = self._update_single_asset(asset)
                
                if success_update:
                    success += 1
                else:
                    failed += 1
                
                # Delay para evitar rate limiting (0.5 seg entre peticiones)
                # Solo si no es el último activo
                if idx < len(assets) - 1:
                    time.sleep(0.5)
            
            except Exception as e:
                failed += 1
                self.errors.append(f"❌ {asset.symbol or asset.name}: {str(e)}")
        
        # Commit de todos los cambios
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise PriceUpdateException(f"Error al guardar precios: {str(e)}")
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def _update_single_asset(self, asset: Asset) -> bool:
        """
        Actualiza un solo activo con datos de Yahoo Finance.
        
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        try:
            ticker = yf.Ticker(asset.yahoo_ticker)
            info = ticker.info
            
            if not info or 'regularMarketPrice' not in info:
                self.errors.append(f"❌ {asset.symbol}: No se encontraron datos en Yahoo Finance")
                return False
            
            # PRECIOS Y CAMBIOS
            asset.current_price = self._safe_get_float(info, 'regularMarketPrice') or \
                                 self._safe_get_float(info, 'currentPrice')
            asset.previous_close = self._safe_get_float(info, 'previousClose') or \
                                   self._safe_get_float(info, 'regularMarketPreviousClose')
            
            # Calcular cambio del día
            if asset.current_price and asset.previous_close and asset.previous_close > 0:
                change = asset.current_price - asset.previous_close
                asset.day_change_percent = (change / asset.previous_close) * 100
            else:
                asset.day_change_percent = None
            
            # VALORACIÓN
            asset.market_cap = self._safe_get_float(info, 'marketCap')
            if asset.market_cap:
                asset.market_cap_formatted = self._format_market_cap(asset.market_cap)
                # Convertir a EUR
                rate = self.EXCHANGE_RATES_TO_EUR.get(asset.currency, 1.0)
                asset.market_cap_eur = asset.market_cap * rate
            
            asset.trailing_pe = self._safe_get_float(info, 'trailingPE')
            asset.forward_pe = self._safe_get_float(info, 'forwardPE')
            
            # INFORMACIÓN CORPORATIVA
            asset.sector = info.get('sector')
            asset.industry = info.get('industry')
            
            # RIESGO Y RENDIMIENTO
            asset.beta = self._safe_get_float(info, 'beta')
            asset.dividend_rate = self._safe_get_float(info, 'dividendRate')
            asset.dividend_yield = self._safe_get_float(info, 'dividendYield')
            if asset.dividend_yield:
                asset.dividend_yield = asset.dividend_yield * 100  # Convertir a porcentaje
            
            # ANÁLISIS DE MERCADO
            asset.recommendation_key = info.get('recommendationKey')
            asset.number_of_analyst_opinions = info.get('numberOfAnalystOpinions')
            asset.target_mean_price = self._safe_get_float(info, 'targetMeanPrice')
            
            # Actualizar timestamp
            asset.last_price_update = datetime.utcnow()
            
            return True
        
        except Exception as e:
            self.errors.append(f"❌ {asset.symbol or asset.name}: {str(e)}")
            return False
    
    def _safe_get_float(self, data: dict, key: str) -> Optional[float]:
        """Obtiene un valor float de forma segura desde un diccionario."""
        try:
            value = data.get(key)
            if value is None or value == 'N/A' or (isinstance(value, float) and (value != value)):  # NaN check
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _format_market_cap(self, market_cap: float) -> str:
        """
        Formatea la capitalización de mercado en formato legible.
        
        Examples:
            1500000000 -> "1.5B"
            234000000 -> "234M"
            45000 -> "45K"
        """
        if market_cap >= 1_000_000_000:
            return f"{market_cap / 1_000_000_000:.1f}B"
        elif market_cap >= 1_000_000:
            return f"{market_cap / 1_000_000:.0f}M"
        elif market_cap >= 1_000:
            return f"{market_cap / 1_000:.0f}K"
        else:
            return f"{market_cap:.0f}"
    
    def get_asset_price(self, asset: Asset) -> Tuple[Optional[float], Optional[str]]:
        """
        Obtiene el precio actual de un activo sin guardar en BD.
        
        Returns:
            Tuple(precio, error_message)
        """
        try:
            if not asset.yahoo_ticker:
                return None, "Sin ticker de Yahoo Finance"
            
            ticker = yf.Ticker(asset.yahoo_ticker)
            info = ticker.info
            
            price = self._safe_get_float(info, 'regularMarketPrice') or \
                   self._safe_get_float(info, 'currentPrice')
            
            if price is None:
                return None, "No se encontraron datos de precio"
            
            return price, None
        
        except Exception as e:
            return None, str(e)
