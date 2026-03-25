"""
PriceUpdater Service - Actualización de precios y métricas desde Yahoo Finance
Sprint 3 Final - Real-time Prices
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import time
import requests
import yfinance as yf
from app import db
from app.models.asset import Asset
from app.services.market_data.exceptions import PriceUpdateException
from app.services.currency_service import convert_to_eur

# Logging para debug
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurar User-Agent para evitar bloqueos de Yahoo Finance
import requests
yf.session = requests.Session()
yf.session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

# Timeouts para evitar colgadas
REQUEST_TIMEOUT = 10  # segundos por request individual
MAX_UPDATE_TIME = 180  # segundos máximos para toda la actualización (3 min)
DELAY_BETWEEN_REQUESTS = 0.5  # segundos entre requests


class PriceUpdater:
    """
    Servicio para actualizar precios y métricas de activos desde Yahoo Finance.
    """
    
    def __init__(self, progress_callback=None, user_id=None):
        """
        Inicializar el servicio de actualización de precios.
        
        Args:
            progress_callback: Función opcional para reportar progreso.
            user_id: Opcional; si se pasa, se usa para registrar llamadas a API en el panel admin.
        """
        self.errors = []
        self.warnings = []
        self.session = None
        self.crumb = None
        self.progress_callback = progress_callback
        self.user_id = user_id
    
    def _authenticate_yahoo(self) -> bool:
        """
        Obtener cookie y crumb de Yahoo Finance para acceder a quoteSummary API.
        
        Returns:
            True si la autenticación fue exitosa, False en caso contrario
        """
        try:
            logger.info("🔐 Autenticando con Yahoo Finance...")
            
            # Crear sesión con headers apropiados
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
            })
            
            # PASO 1: Obtener cookie
            response = self.session.get('https://finance.yahoo.com', timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                logger.error(f"   ❌ Error al obtener cookie: HTTP {response.status_code}")
                return False
            
            if len(self.session.cookies) == 0:
                logger.error(f"   ❌ No se recibieron cookies")
                return False
            
            logger.info(f"   ✅ Cookie obtenido ({len(self.session.cookies)} cookies)")
            
            # PASO 2: Obtener crumb
            time.sleep(DELAY_BETWEEN_REQUESTS)  # Pequeña pausa entre requests
            crumb_response = self.session.get(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                timeout=REQUEST_TIMEOUT
            )
            
            if crumb_response.status_code != 200:
                logger.error(f"   ❌ Error al obtener crumb: HTTP {crumb_response.status_code}")
                return False
            
            self.crumb = crumb_response.text.strip()
            
            if not self.crumb or self.crumb == "null" or "Too Many Requests" in self.crumb:
                logger.error(f"   ❌ Crumb inválido: {self.crumb}")
                return False
            
            logger.info(f"   ✅ Crumb obtenido: {self.crumb[:10]}...")
            return True
            
        except Exception as e:
            logger.error(f"   ❌ Error en autenticación: {e}")
            return False
    
    def update_asset_prices(self, asset_ids: Optional[List[int]] = None, user_id: Optional[int] = None) -> Dict:
        """
        Actualiza precios de uno o varios activos.

        Args:
            asset_ids: Lista de IDs de activos. Si None, actualiza activos con holdings > 0.
            user_id: Si se indica, solo se consideran posiciones de ese usuario (evita escanear activos de otros usuarios).
        Returns:
            Dict con estadísticas de la actualización
        """
        self.errors = []
        self.warnings = []
        self.failed_assets = []   # [{ asset_id, symbol, name, isin, error }, ...]
        self.skipped_assets = []  # [{ asset_id, symbol, name, isin, error }, ...]

        # Obtener activos a actualizar (excluir activos con baja de cotización ya efectiva)
        from app.services.delisting_reconciliation_service import get_delisted_asset_ids
        delisted_asset_ids = get_delisted_asset_ids()

        if asset_ids:
            assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
        else:
            # Actualizar solo activos con posiciones actuales (del usuario si se indica user_id)
            from app.models.portfolio import PortfolioHolding
            q = db.session.query(PortfolioHolding.asset_id).filter(PortfolioHolding.quantity > 0)
            if user_id is not None:
                q = q.filter(PortfolioHolding.user_id == user_id)
            asset_ids_with_holdings = q.distinct().all()
            asset_ids_with_holdings = [a[0] for a in asset_ids_with_holdings]
            assets = Asset.query.filter(Asset.id.in_(asset_ids_with_holdings)).all()

        assets = [a for a in assets if a.id not in delisted_asset_ids]

        if not assets:
            logger.info("⚠️ No hay activos para actualizar")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [],
                'warnings': [],
                'failed_assets': [],
                'skipped_assets': [],
            }
        
        total = len(assets)
        success = 0
        failed = 0
        skipped = 0
        
        logger.info("=" * 80)
        logger.info(f"🔄 INICIANDO ACTUALIZACIÓN DE PRECIOS")
        logger.info(f"📊 Total de activos a procesar: {total}")
        logger.info("=" * 80)
        
        # Reportar inicio (si hay callback)
        if self.progress_callback:
            self.progress_callback({
                'current': 0,
                'total': total,
                'current_asset': 'Autenticando con Yahoo Finance...',
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'errors': []
            })
        
        # Autenticar con Yahoo Finance para acceder a quoteSummary
        auth_success = self._authenticate_yahoo()
        if not auth_success:
            logger.warning("⚠️ No se pudo autenticar con Yahoo Finance")
            logger.warning("   Solo se actualizarán precios básicos (sin sector/industry)")
        logger.info("")
        
        # Timer para timeout máximo
        start_time = time.time()
        
        for idx, asset in enumerate(assets):
            # Verificar timeout máximo
            elapsed_time = time.time() - start_time
            if elapsed_time > MAX_UPDATE_TIME:
                remaining = len(assets) - idx
                logger.warning(f"⏱️ TIMEOUT: Se alcanzó el límite de {MAX_UPDATE_TIME}s")
                logger.warning(f"   {remaining} assets restantes no se actualizarán")
                self.warnings.append(f"Timeout: {remaining} assets no procesados por límite de tiempo")
                break
            logger.info(f"\n{'='*60}")
            logger.info(f"📈 [{idx+1}/{total}] Procesando: {asset.symbol or asset.name}")
            logger.info(f"   ISIN: {asset.isin}")
            logger.info(f"   Yahoo Ticker: {asset.yahoo_ticker or 'N/A'}")
            
            try:
                # Verificar que tenga ticker válido
                if not asset.yahoo_ticker:
                    skipped += 1
                    err_msg = "Sin ticker de Yahoo Finance"
                    logger.warning(f"   ⚠️ OMITIDO: {err_msg}")
                    self.warnings.append(f"❌ {asset.symbol or asset.name}: {err_msg}")
                    self.skipped_assets.append({
                        'asset_id': asset.id,
                        'symbol': asset.symbol or '',
                        'name': asset.name or '',
                        'isin': asset.isin or '',
                        'error': err_msg,
                        'currency': asset.currency or 'EUR',
                    })
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
                    last_error = self.errors[-1] if self.errors else "Error desconocido"
                    self.failed_assets.append({
                        'asset_id': asset.id,
                        'symbol': asset.symbol or '',
                        'name': asset.name or '',
                        'isin': asset.isin or '',
                        'error': last_error.replace('❌ ', '').strip(),
                        'currency': asset.currency or 'EUR',
                    })
                
                # Reportar progreso (si hay callback)
                if self.progress_callback:
                    self.progress_callback({
                        'current': idx + 1,
                        'total': total,
                        'current_asset': f"{asset.symbol or asset.name}",
                        'success': success,
                        'failed': failed,
                        'skipped': skipped,
                        'errors': self.errors[-3:] if len(self.errors) > 0 else []  # Últimos 3 errores
                    })
                
                # Delay para evitar rate limiting
                # Solo si no es el último activo
                if idx < len(assets) - 1:
                    logger.info(f"   ⏳ Esperando {DELAY_BETWEEN_REQUESTS}s antes del siguiente...")
                    time.sleep(DELAY_BETWEEN_REQUESTS)
            
            except Exception as e:
                failed += 1
                error_msg = str(e)
                logger.error(f"   ❌ ERROR: {error_msg}")
                self.errors.append(f"❌ {asset.symbol or asset.name}: {error_msg}")
                self.failed_assets.append({
                    'asset_id': asset.id,
                    'symbol': asset.symbol or '',
                    'name': asset.name or '',
                    'isin': asset.isin or '',
                    'error': error_msg[:120],
                    'currency': asset.currency or 'EUR',
                })
                
                # Reportar error en progreso
                if self.progress_callback:
                    self.progress_callback({
                        'current': idx + 1,
                        'total': total,
                        'current_asset': f"{asset.symbol or asset.name} (error)",
                        'success': success,
                        'failed': failed,
                        'skipped': skipped,
                        'errors': self.errors[-3:]
                    })
        
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
            'warnings': self.warnings,
            'failed_assets': self.failed_assets,
            'skipped_assets': self.skipped_assets,
        }
    
    def _update_single_asset(self, asset: Asset) -> bool:
        """
        Actualiza un solo activo con datos de Yahoo Finance usando la Chart API directa.
        
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        try:
            logger.debug(f"      Consultando Chart API para {asset.yahoo_ticker}")
            
            # Usar API directa en vez de yfinance.info (evita problemas con crumbs/cookies)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{asset.yahoo_ticker}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                logger.debug(f"      ✓ Respuesta recibida: {response.status_code}")
            except requests.exceptions.HTTPError as http_error:
                logger.error(f"      ❌ Error HTTP: {http_error}")
                if response.status_code == 404:
                    self.errors.append(f"❌ {asset.symbol}: Símbolo no encontrado en Yahoo Finance")
                else:
                    self.errors.append(f"❌ {asset.symbol}: Error HTTP {response.status_code}")
                return False
            except Exception as req_error:
                logger.error(f"      ❌ Error en request: {req_error}")
                raise
            
            # Parsear respuesta JSON
            try:
                data = response.json()
                logger.debug(f"      ✓ JSON parseado correctamente")
            except Exception as json_error:
                logger.error(f"      ❌ Error al parsear JSON: {json_error}")
                self.errors.append(f"❌ {asset.symbol}: Respuesta inválida de Yahoo Finance")
                return False
            
            # Verificar si hay error en la respuesta
            if data.get('chart', {}).get('error'):
                error_msg = data['chart']['error'].get('description', 'Error desconocido')
                logger.warning(f"      ⚠️ Error de API: {error_msg}")
                self.errors.append(f"❌ {asset.symbol}: {error_msg}")
                return False
            
            # Extraer datos del chart
            if not data.get('chart', {}).get('result'):
                logger.warning(f"      ⚠️ Sin resultados en chart")
                self.errors.append(f"❌ {asset.symbol}: No hay datos disponibles")
                return False
            
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            
            logger.debug(f"      Meta keys disponibles: {list(meta.keys())}")
            
            # Verificar que tengamos precio
            if 'regularMarketPrice' not in meta:
                logger.warning(f"      ⚠️ No se encontró precio en meta")
                self.errors.append(f"❌ {asset.symbol}: No se encontró precio")
                return False
            
            # PRECIOS Y CAMBIOS (desde Chart API)
            asset.current_price = self._safe_get_float(meta, 'regularMarketPrice')
            asset.previous_close = self._safe_get_float(meta, 'chartPreviousClose') or \
                                   self._safe_get_float(meta, 'previousClose')
            
            # Calcular cambio del día
            if asset.current_price and asset.previous_close and asset.previous_close > 0:
                change = asset.current_price - asset.previous_close
                asset.day_change_percent = (change / asset.previous_close) * 100
                logger.debug(f"      ✓ Precio: {asset.current_price}, Cambio: {asset.day_change_percent:+.2f}%")
            else:
                asset.day_change_percent = None
            
            # Actualizar timestamp
            asset.last_price_update = datetime.utcnow()

            try:
                from app.services.api_log_service import log_api_call
                log_api_call(
                    api_name='yahoo_chart',
                    endpoint_or_operation=url,
                    response_status=200,
                    value_reported={'ticker': asset.yahoo_ticker, 'price': asset.current_price},
                    user_id=getattr(self, 'user_id', None),
                )
            except Exception:
                pass
            
            # Si tenemos autenticación, obtener datos avanzados de quoteSummary
            if self.session and self.crumb:
                logger.debug(f"      📊 Consultando quoteSummary para datos avanzados...")
                try:
                    quote_url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{asset.yahoo_ticker}"
                    params = {
                        'modules': 'assetProfile,summaryDetail,defaultKeyStatistics,financialData',
                        'crumb': self.crumb
                    }
                    
                    quote_response = self.session.get(quote_url, params=params, timeout=REQUEST_TIMEOUT)
                    
                    if quote_response.status_code == 200:
                        try:
                            from app.services.api_log_service import log_api_call
                            log_api_call(
                                api_name='yahoo_quote',
                                endpoint_or_operation=quote_url,
                                response_status=200,
                                value_reported={'ticker': asset.yahoo_ticker},
                                user_id=getattr(self, 'user_id', None),
                            )
                        except Exception:
                            pass
                        quote_data = quote_response.json()
                        
                        if 'quoteSummary' in quote_data and quote_data['quoteSummary'].get('result'):
                            result = quote_data['quoteSummary']['result'][0]
                            
                            # SECTOR, INDUSTRY Y COUNTRY (assetProfile)
                            if 'assetProfile' in result:
                                profile = result['assetProfile']
                                asset.sector = profile.get('sector')
                                asset.industry = profile.get('industry')
                                asset.country = profile.get('country')
                                logger.debug(f"      ✅ Sector: {asset.sector}, Industry: {asset.industry}, Country: {asset.country}")
                            
                            # VALORACIÓN (summaryDetail + defaultKeyStatistics)
                            summary = result.get('summaryDetail', {})
                            stats = result.get('defaultKeyStatistics', {})
                            
                            # Market Cap
                            market_cap_raw = summary.get('marketCap', {}).get('raw')
                            if market_cap_raw:
                                asset.market_cap = float(market_cap_raw)
                                asset.market_cap_formatted = self._format_market_cap(asset.market_cap)
                                # Convertir a EUR usando servicio de divisas (con cache)
                                asset.market_cap_eur = convert_to_eur(asset.market_cap, asset.currency)
                                logger.debug(f"      💰 Market Cap: {asset.market_cap_formatted}")
                            
                            # P/E Ratios
                            asset.trailing_pe = self._safe_get_float(summary, 'trailingPE')
                            asset.forward_pe = self._safe_get_float(stats, 'forwardPE')
                            if asset.trailing_pe:
                                logger.debug(f"      📊 P/E (trailing): {asset.trailing_pe:.2f}")
                            
                            # RIESGO Y RENDIMIENTO
                            asset.beta = self._safe_get_float(stats, 'beta')
                            
                            # Dividendos
                            div_rate_raw = summary.get('dividendRate', {})
                            if isinstance(div_rate_raw, dict):
                                asset.dividend_rate = div_rate_raw.get('raw')
                            
                            div_yield_raw = summary.get('dividendYield', {})
                            if isinstance(div_yield_raw, dict):
                                div_yield = div_yield_raw.get('raw')
                                if div_yield:
                                    asset.dividend_yield = div_yield * 100  # Convertir a porcentaje
                            
                            if asset.dividend_yield:
                                logger.debug(f"      💵 Dividend Yield: {asset.dividend_yield:.2f}%")
                            
                            # ANÁLISIS DE MERCADO (financialData)
                            financial = result.get('financialData', {})
                            asset.recommendation_key = financial.get('recommendationKey')
                            
                            # number_of_analyst_opinions puede ser un dict o un número
                            num_analysts = financial.get('numberOfAnalystOpinions')
                            if isinstance(num_analysts, dict):
                                asset.number_of_analyst_opinions = num_analysts.get('raw')
                            elif isinstance(num_analysts, (int, float)):
                                asset.number_of_analyst_opinions = int(num_analysts)
                            else:
                                asset.number_of_analyst_opinions = None
                            
                            target_price_raw = financial.get('targetMeanPrice', {})
                            if isinstance(target_price_raw, dict):
                                asset.target_mean_price = target_price_raw.get('raw')
                            
                            if asset.recommendation_key:
                                logger.debug(f"      🎯 Recomendación: {asset.recommendation_key}")
                            
                            logger.debug(f"      ✅ Datos avanzados obtenidos")
                        else:
                            logger.debug(f"      ⚠️ quoteSummary sin resultados")
                    else:
                        logger.debug(f"      ⚠️ quoteSummary HTTP {quote_response.status_code}")
                        
                except Exception as e:
                    logger.debug(f"      ⚠️ Error en quoteSummary: {e}")
                    # No falla el update si quoteSummary falla
            
            logger.debug(f"      ✓ Asset actualizado correctamente")
            
            return True
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"      ❌ EXCEPCIÓN CAPTURADA:")
            logger.error(f"      Tipo: {type(e).__name__}")
            logger.error(f"      Mensaje: {str(e)}")
            logger.error(f"      Traceback completo:")
            for line in error_detail.split('\n'):
                if line.strip():
                    logger.error(f"         {line}")
            self.errors.append(f"❌ {asset.symbol}: {str(e)}")
            return False
    
    def _safe_get_float(self, data: dict, key: str) -> Optional[float]:
        """Obtiene un valor float de forma segura desde un diccionario."""
        try:
            value = data.get(key)
            if value is None:
                return None
            
            # Yahoo Finance a veces devuelve {raw: valor, fmt: "string"}
            if isinstance(value, dict):
                value = value.get('raw')
                if value is None:
                    return None
            
            if value == 'N/A' or (isinstance(value, float) and (value != value)):  # NaN check
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
    
    def update_single_asset_price_only(self, asset: Asset) -> bool:
        """
        Actualiza solo precio básico (Chart API). Sin autenticación, sin quoteSummary.
        Usado por el job de polling en segundo plano.
        Actualiza: current_price, previous_close, day_change_percent, last_price_update.
        Returns True si OK.
        """
        try:
            if not asset.yahoo_ticker:
                return False
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{asset.yahoo_ticker}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('chart', {}).get('error'):
                return False
            if not data.get('chart', {}).get('result'):
                return False
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            if 'regularMarketPrice' not in meta:
                return False
            asset.current_price = self._safe_get_float(meta, 'regularMarketPrice')
            asset.previous_close = self._safe_get_float(meta, 'chartPreviousClose') or \
                                   self._safe_get_float(meta, 'previousClose')
            if asset.current_price and asset.previous_close and asset.previous_close > 0:
                change = asset.current_price - asset.previous_close
                asset.day_change_percent = (change / asset.previous_close) * 100
            else:
                asset.day_change_percent = None
            asset.last_price_update = datetime.utcnow()
            try:
                from app.services.api_log_service import log_api_call
                log_api_call(
                    api_name='yahoo_chart',
                    endpoint_or_operation=url,
                    response_status=200,
                    value_reported={'ticker': asset.yahoo_ticker, 'price': asset.current_price},
                    user_id=getattr(self, 'user_id', None),
                )
            except Exception:
                pass
            return True
        except Exception:
            return False

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
