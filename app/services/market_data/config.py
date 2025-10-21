"""
Configuración centralizada para Market Data Services
"""

# OpenFIGI API
OPENFIGI_URL = 'https://api.openfigi.com/v3/mapping'
OPENFIGI_RATE_LIMIT_DELAY = 2.5  # segundos entre llamadas (OpenFIGI limit: 25 req/min = 1 cada 2.4s)
OPENFIGI_TIMEOUT = 10  # segundos

# Yahoo Finance
YAHOO_RATE_LIMIT_DELAY = 0.1  # segundos entre llamadas
YAHOO_TIMEOUT = 10  # segundos

# Cache
ENABLE_CACHE = True
CACHE_TTL = 86400  # 24 horas para datos de assets
PRICE_CACHE_TTL = 300  # 5 minutos para precios

