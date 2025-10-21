"""
Yahoo Finance Provider para actualización de precios
"""
import re
import yfinance as yf
from datetime import datetime
from time import sleep
from typing import Optional, Dict
from ..interfaces.price_provider import PriceProvider
from ..exceptions import ProviderException, AssetNotFoundException
from ..config import YAHOO_RATE_LIMIT_DELAY, YAHOO_TIMEOUT

class YahooFinanceProvider(PriceProvider):
    """
    Provider para obtener precios usando Yahoo Finance
    """
    
    def __init__(self):
        self.rate_limit_delay = YAHOO_RATE_LIMIT_DELAY
        self.timeout = YAHOO_TIMEOUT
        self.cache = {}
    
    def get_current_price(self, symbol: str, suffix: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene el precio actual de un asset desde Yahoo Finance
        
        Args:
            symbol: Símbolo del asset (ticker)
            suffix: Sufijo opcional (ej: '.MC' para Yahoo Finance)
            
        Returns:
            Dict con datos del precio o None si no se encuentra
        """
        # Construir ticker completo
        ticker = symbol
        if suffix:
            ticker = f"{symbol}{suffix}"
        
        # Check cache (TTL 5 minutos)
        cache_key = ticker
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).seconds < 300:  # 5 minutos
                return cached_data
        
        try:
            # Obtener datos de Yahoo Finance
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            # Verificar que tengamos datos válidos
            if not info or 'symbol' not in info:
                raise AssetNotFoundException(f"Asset {ticker} not found in Yahoo Finance")
            
            # Obtener precio actual
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if not current_price:
                # Intentar obtener el último precio de cierre
                hist = ticker_obj.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            if not current_price:
                return None
            
            # Construir respuesta
            price_data = {
                'price': float(current_price),
                'currency': info.get('currency', 'USD'),
                'timestamp': datetime.now(),
                'open': info.get('regularMarketOpen'),
                'high': info.get('dayHigh') or info.get('regularMarketDayHigh'),
                'low': info.get('dayLow') or info.get('regularMarketDayLow'),
                'volume': info.get('volume') or info.get('regularMarketVolume'),
                'change': info.get('regularMarketChange'),
                'change_percent': info.get('regularMarketChangePercent'),
                'previous_close': info.get('previousClose') or info.get('regularMarketPreviousClose'),
                'market_cap': info.get('marketCap'),
                'ticker': ticker,
            }
            
            # Cache result
            self.cache[cache_key] = (price_data, datetime.now())
            
            # Rate limiting
            sleep(self.rate_limit_delay)
            
            return price_data
        
        except Exception as e:
            raise ProviderException(f"Error getting price for {ticker}: {str(e)}")
    
    def parse_yahoo_url(self, url: str) -> Optional[Dict]:
        """
        Parsea una URL de Yahoo Finance para extraer symbol y suffix
        
        Ejemplos de URLs válidas:
        - https://es.finance.yahoo.com/quote/PSG.MC/
        - https://finance.yahoo.com/quote/AAPL
        - https://uk.finance.yahoo.com/quote/VOD.L/
        
        Args:
            url: URL de Yahoo Finance
            
        Returns:
            Dict con symbol y suffix o None si no es válida
            {
                'symbol': str,  # 'PSG', 'AAPL', 'VOD'
                'suffix': str,  # '.MC', '', '.L'
                'full_ticker': str  # 'PSG.MC', 'AAPL', 'VOD.L'
            }
        """
        # Pattern para URLs de Yahoo Finance
        # Captura: /quote/TICKER o /quote/TICKER/ o /quote/TICKER?...
        pattern = r'finance\.yahoo\.com/quote/([A-Z0-9\.\-\^]+)'
        
        match = re.search(pattern, url, re.IGNORECASE)
        
        if not match:
            return None
        
        full_ticker = match.group(1).strip('/')
        
        # Separar symbol y suffix
        if '.' in full_ticker:
            parts = full_ticker.rsplit('.', 1)
            symbol = parts[0]
            suffix = f".{parts[1]}"
        else:
            symbol = full_ticker
            suffix = ''
        
        return {
            'symbol': symbol,
            'suffix': suffix,
            'full_ticker': full_ticker
        }
    
    def validate_ticker(self, symbol: str, suffix: Optional[str] = None) -> bool:
        """
        Valida que un ticker existe en Yahoo Finance
        
        Args:
            symbol: Símbolo del asset
            suffix: Sufijo opcional
            
        Returns:
            True si el ticker es válido, False en caso contrario
        """
        try:
            price_data = self.get_current_price(symbol, suffix)
            return price_data is not None
        except:
            return False

