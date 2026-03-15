"""
Currency Conversion Service - Real-time exchange rates
Uses European Central Bank (ECB) API with 24h cache
"""
import requests
import time
from datetime import datetime, timedelta
from threading import Lock
import logging

logger = logging.getLogger(__name__)

# Cache global (thread-safe)
_exchange_rates_cache = {
    'rates': None,
    'last_update': None,
    'ttl': 24 * 60 * 60  # 24 horas en segundos
}
_cache_lock = Lock()


def clear_rates_cache():
    """
    Vacía el cache de tasas de cambio (in-memory).
    La siguiente llamada a get_exchange_rates() volverá a llamar a la API.
    Útil para pruebas: mismo proceso debe llamar esto y luego recalcular métricas.
    """
    with _cache_lock:
        _exchange_rates_cache['rates'] = None
        _exchange_rates_cache['last_update'] = None
    logger.info("Cache de tasas de cambio vaciado.")


# Alias de monedas incorrectos -> códigos ISO 4217
# BG es código país (Bulgaria), la moneda correcta es BGN (Lev búlgaro)
CURRENCY_ALIASES = {
    'BG': 'BGN',   # Bulgaria - común en ISINs que empiezan por BG
}

# Tasas de fallback (si API falla)
FALLBACK_RATES = {
    'EUR': 1.0,
    'USD': 0.92,
    'GBP': 1.17,
    'BGN': 0.51,   # Lev búlgaro
    'JPY': 0.0062,
    'CHF': 1.06,
    'AUD': 0.60,
    'CAD': 0.67,
    'HKD': 0.12,
    'SGD': 0.68,
    'NOK': 0.086,
    'SEK': 0.085,
    'DKK': 0.13,
    'PLN': 0.23,
    'GBX': 0.012,
}


def get_exchange_rates(force_refresh=False):
    """
    Obtiene tasas de cambio a EUR desde el BCE.
    Usa cache de 24 horas para rendimiento.
    
    Args:
        force_refresh: Si True, fuerza actualización ignorando cache
        
    Returns:
        Dict con tasas de cambio a EUR. Ejemplo: {'USD': 0.92, 'GBP': 1.17, ...}
    """
    with _cache_lock:
        # Verificar si el cache es válido
        if not force_refresh and _is_cache_valid():
            # Cache hit - no logging para evitar saturar logs
            return _exchange_rates_cache['rates']
        
        # Cache expirado o no existe, obtener tasas frescas
        logger.info("🔄 Actualizando tasas de cambio desde ECB...")
        
        try:
            # Llamar a la API del BCE
            rates = _fetch_rates_from_ecb()
            
            # Actualizar cache
            _exchange_rates_cache['rates'] = rates
            _exchange_rates_cache['last_update'] = time.time()
            
            logger.info(f"✅ Tasas actualizadas correctamente ({len(rates)} monedas)")
            return rates
            
        except Exception as e:
            logger.error(f"❌ Error al obtener tasas del BCE: {e}")
            logger.warning("⚠️ Usando tasas de fallback")
            
            # Si hay cache antiguo, usarlo aunque esté expirado
            if _exchange_rates_cache['rates']:
                logger.info("📊 Usando cache antiguo como fallback")
                return _exchange_rates_cache['rates']
            
            # Si no hay cache, usar tasas hardcoded
            return FALLBACK_RATES


def _is_cache_valid():
    """Verifica si el cache es válido (no ha expirado)"""
    if _exchange_rates_cache['rates'] is None:
        return False
    
    if _exchange_rates_cache['last_update'] is None:
        return False
    
    elapsed = time.time() - _exchange_rates_cache['last_update']
    is_valid = elapsed < _exchange_rates_cache['ttl']
    
    if not is_valid:
        logger.debug(f"⏰ Cache expirado (edad: {elapsed/3600:.1f}h)")
    
    return is_valid


def _fetch_rates_from_ecb():
    """
    Obtiene tasas desde exchangerate-api.com (GRATIS, sin API key).
    
    API: https://api.exchangerate-api.com/v4/latest/EUR
    - Gratis, sin API key, sin límites
    - Actualización diaria
    - Base: EUR
    
    Returns:
        Dict con tasas inversas (de cada moneda a EUR)
    """
    url = "https://api.exchangerate-api.com/v4/latest/EUR"
    
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    
    data = response.json()
    
    rates_from_eur = data.get('rates', {})
    
    if not rates_from_eur:
        raise Exception("No rates returned from API")
    
    # Invertir las tasas (de EUR→X a X→EUR)
    # Ejemplo: EUR→USD = 1.09 → USD→EUR = 1/1.09 = 0.92
    rates_to_eur = {}
    for currency, rate in rates_from_eur.items():
        if rate > 0:
            rates_to_eur[currency] = 1 / rate
    
    # Asegurar que EUR = 1.0
    rates_to_eur['EUR'] = 1.0
    
    # Añadir GBX (UK Pence) si no está
    # GBX = 1/100 de GBP
    if 'GBX' not in rates_to_eur and 'GBP' in rates_to_eur:
        rates_to_eur['GBX'] = rates_to_eur['GBP'] / 100

    try:
        from app.services.api_log_service import log_api_call
        log_api_call(
            api_name='exchangerate',
            endpoint_or_operation=url,
            response_status=response.status_code,
            value_reported={'currencies': len(rates_to_eur)},
        )
    except Exception:
        pass

    return rates_to_eur


def _normalize_currency(currency: str) -> str:
    """Resuelve alias (ej: BG -> BGN) para códigos mal escritos o truncados."""
    if not currency:
        return ''
    cu = currency.upper()
    return CURRENCY_ALIASES.get(cu, cu)


def convert_to_eur(amount, currency):
    """
    Convierte una cantidad en cualquier moneda a EUR.
    
    Args:
        amount: Cantidad a convertir
        currency: Código de moneda (ej: 'USD', 'GBP', 'BGN', etc.)
        
    Returns:
        Cantidad equivalente en EUR
        
    Example:
        >>> convert_to_eur(100, 'USD')
        92.0  # (100 USD = 92 EUR aproximadamente)
    """
    if not amount or not currency:
        return 0.0
    
    # Obtener tasas (usa cache si está disponible)
    rates = get_exchange_rates()
    
    # Resolver alias (BG -> BGN, etc.)
    currency_upper = _normalize_currency(currency)
    rate = rates.get(currency_upper)
    
    if rate is None:
        logger.warning(f"⚠️ Moneda no encontrada: {currency_upper}, usando tasa 1.0")
        rate = 1.0
    
    return amount * rate


def get_cache_info():
    """
    Obtiene información del estado del cache (para debugging).
    
    Returns:
        Dict con información del cache
    """
    with _cache_lock:
        if _exchange_rates_cache['last_update']:
            last_update_dt = datetime.fromtimestamp(_exchange_rates_cache['last_update'])
            age_seconds = time.time() - _exchange_rates_cache['last_update']
            age_hours = age_seconds / 3600
            
            return {
                'is_valid': _is_cache_valid(),
                'last_update': last_update_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'age_hours': round(age_hours, 1),
                'ttl_hours': _exchange_rates_cache['ttl'] / 3600,
                'currencies_count': len(_exchange_rates_cache['rates']) if _exchange_rates_cache['rates'] else 0
            }
        else:
            return {
                'is_valid': False,
                'last_update': 'Never',
                'age_hours': None,
                'ttl_hours': _exchange_rates_cache['ttl'] / 3600,
                'currencies_count': 0
            }

