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

# Logging para debug
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            logger.info("⚠️ No hay activos para actualizar")
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
        
        logger.info("=" * 80)
        logger.info(f"🔄 INICIANDO ACTUALIZACIÓN DE PRECIOS")
        logger.info(f"📊 Total de activos a procesar: {total}")
        logger.info("=" * 80)
        
        for idx, asset in enumerate(assets):
            logger.info(f"\n{'='*60}")
            logger.info(f"📈 [{idx+1}/{total}] Procesando: {asset.symbol or asset.name}")
            logger.info(f"   ISIN: {asset.isin}")
            logger.info(f"   Yahoo Ticker: {asset.yahoo_ticker or 'N/A'}")
            
            try:
                # Verificar que tenga ticker válido
                if not asset.yahoo_ticker:
                    skipped += 1
                    logger.warning(f"   ⚠️ OMITIDO: Sin ticker de Yahoo Finance")
                    self.warnings.append(f"❌ {asset.symbol or asset.name}: Sin ticker de Yahoo Finance")
                    continue
                
                logger.info(f"   🔍 Consultando Yahoo Finance: {asset.yahoo_ticker}")
                
                # Obtener datos de Yahoo Finance
                start_time = time.time()
                success_update = self._update_single_asset(asset)
                elapsed = time.time() - start_time
                
                if success_update:
                    success += 1
                    logger.info(f"   ✅ ÉXITO (en {elapsed:.2f}s)")
                    if asset.current_price:
                        logger.info(f"   💰 Precio actualizado: {asset.current_price} {asset.currency}")
                        if asset.day_change_percent:
                            logger.info(f"   📊 Cambio del día: {asset.day_change_percent:+.2f}%")
                else:
                    failed += 1
                    logger.error(f"   ❌ FALLÓ (en {elapsed:.2f}s)")
                
                # Delay para evitar rate limiting (1.5 seg entre peticiones)
                # Solo si no es el último activo
                if idx < len(assets) - 1:
                    logger.info(f"   ⏳ Esperando 1.5s antes del siguiente...")
                    time.sleep(1.5)
            
            except Exception as e:
                failed += 1
                error_msg = str(e)
                logger.error(f"   ❌ ERROR: {error_msg}")
                self.errors.append(f"❌ {asset.symbol or asset.name}: {error_msg}")
        
        # Commit de todos los cambios
        logger.info("\n" + "=" * 80)
        logger.info("💾 Guardando cambios en base de datos...")
        try:
            db.session.commit()
            logger.info("✅ Cambios guardados correctamente")
        except Exception as e:
            logger.error(f"❌ Error al guardar: {str(e)}")
            db.session.rollback()
            raise PriceUpdateException(f"Error al guardar precios: {str(e)}")
        
        # Resumen final
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMEN FINAL:")
        logger.info(f"   ✅ Exitosos: {success}/{total}")
        logger.info(f"   ❌ Fallidos: {failed}/{total}")
        logger.info(f"   ⚠️ Omitidos: {skipped}/{total}")
        logger.info("=" * 80)
        
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
            logger.debug(f"      Creando objeto Ticker para {asset.yahoo_ticker}")
            ticker = yf.Ticker(asset.yahoo_ticker)
            
            logger.debug(f"      Obteniendo info...")
            info = ticker.info
            
            logger.debug(f"      Info obtenida: {len(info)} campos")
            
            if not info or 'regularMarketPrice' not in info:
                logger.warning(f"      ⚠️ Info vacía o sin precio (keys: {list(info.keys())[:5]}...)")
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
