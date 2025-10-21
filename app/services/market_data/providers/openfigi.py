"""
OpenFIGI Provider para enriquecimiento de assets
Estrategia simple: ISIN + Currency → Tomar primer resultado
"""
import requests
import json
from time import sleep
from typing import Optional, Dict
from ..interfaces.enrichment_provider import EnrichmentProvider
from ..exceptions import ProviderException, RateLimitException, AssetNotFoundException
from ..config import OPENFIGI_URL, OPENFIGI_RATE_LIMIT_DELAY, OPENFIGI_TIMEOUT

class OpenFIGIProvider(EnrichmentProvider):
    """
    Provider para enriquecer assets usando OpenFIGI API
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: API key de OpenFIGI (opcional, pero recomendado para rate limits más altos)
        """
        self.api_key = api_key
        self.base_url = OPENFIGI_URL
        self.rate_limit_delay = OPENFIGI_RATE_LIMIT_DELAY
        self.timeout = OPENFIGI_TIMEOUT
        self.cache = {}
    
    def enrich_by_isin(self, isin: str, currency: Optional[str] = None) -> Optional[Dict]:
        """
        Enriquece un asset usando su ISIN
        Estrategia simple: ISIN + Currency → Primer resultado
        
        Args:
            isin: Código ISIN del asset
            currency: Moneda opcional para filtrar resultados
            
        Returns:
            Dict con datos del asset o None si no se encuentra
        """
        # Check cache
        cache_key = f"{isin}_{currency or 'NONE'}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Construir query
        query = {
            'idType': 'ID_ISIN',
            'idValue': isin
        }
        
        if currency:
            query['currency'] = currency
        
        # Hacer request
        try:
            results = self._query_openfigi(query)
            
            if not results:
                return None
            
            # Estrategia simple: Tomar el primer resultado
            first_result = results[0]
            
            # Mapear a formato interno
            enriched_data = {
                'symbol': first_result.get('ticker'),
                'name': first_result.get('name'),
                'exchange': first_result.get('exchCode'),  # Código interno OpenFIGI
                'mic': first_result.get('micCode'),  # MIC ISO 10383 (puede ser None)
                'currency': first_result.get('currency'),
                'asset_type': self._map_security_type(first_result.get('securityType')),
                'sector': first_result.get('marketSector'),
                'composite_figi': first_result.get('compositeFIGI'),
                'figi': first_result.get('figi'),
                'security_type_2': first_result.get('securityType2'),
            }
            
            # Cache result
            self.cache[cache_key] = enriched_data
            
            # Rate limiting
            sleep(self.rate_limit_delay)
            
            return enriched_data
        
        except RateLimitException:
            # OpenFIGI rate limit alcanzado, esperar 60 segundos
            print(f"⚠️  OpenFIGI rate limit alcanzado para {isin}. Esperando 60s...")
            sleep(60)
            print(f"✓ Reintentando {isin}...")
            return self.enrich_by_isin(isin, currency)
        
        except Exception as e:
            raise ProviderException(f"Error enriching asset by ISIN {isin}: {str(e)}")
    
    def enrich_by_symbol(self, symbol: str, exchange: Optional[str] = None) -> Optional[Dict]:
        """
        Enriquece un asset usando su símbolo
        
        Args:
            symbol: Símbolo del asset (ticker)
            exchange: Exchange opcional para filtrar resultados
            
        Returns:
            Dict con datos del asset o None si no se encuentra
        """
        # Construir query
        query = {
            'idType': 'TICKER',
            'idValue': symbol
        }
        
        if exchange:
            query['exchCode'] = exchange
        
        # Hacer request
        try:
            results = self._query_openfigi(query)
            
            if not results:
                return None
            
            # Tomar el primer resultado
            first_result = results[0]
            
            # Mapear a formato interno
            enriched_data = {
                'symbol': first_result.get('ticker'),
                'name': first_result.get('name'),
                'isin': None,  # No disponible en búsqueda por ticker
                'exchange': first_result.get('exchCode'),
                'mic': first_result.get('micCode'),
                'currency': first_result.get('currency'),
                'asset_type': self._map_security_type(first_result.get('securityType')),
                'sector': first_result.get('marketSector'),
                'composite_figi': first_result.get('compositeFIGI'),
                'figi': first_result.get('figi'),
            }
            
            # Rate limiting
            sleep(self.rate_limit_delay)
            
            return enriched_data
        
        except RateLimitException:
            # OpenFIGI rate limit alcanzado, esperar 60 segundos
            print(f"⚠️  OpenFIGI rate limit alcanzado para {symbol}. Esperando 60s...")
            sleep(60)
            print(f"✓ Reintentando {symbol}...")
            return self.enrich_by_symbol(symbol, exchange)
        
        except Exception as e:
            raise ProviderException(f"Error enriching asset by symbol {symbol}: {str(e)}")
    
    def _query_openfigi(self, query: Dict) -> list:
        """
        Ejecuta una query a OpenFIGI API
        
        Args:
            query: Dict con parámetros de búsqueda
            
        Returns:
            Lista de resultados
        """
        headers = {'Content-Type': 'application/json'}
        
        if self.api_key:
            headers['X-OPENFIGI-APIKEY'] = self.api_key
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                data=json.dumps([query]),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data and isinstance(data, list) and len(data) > 0:
                    if 'data' in data[0]:
                        return data[0]['data']
                    elif 'error' in data[0]:
                        error_msg = data[0]['error']
                        if 'No identifier found' in error_msg:
                            raise AssetNotFoundException(error_msg)
                        else:
                            raise ProviderException(f"OpenFIGI error: {error_msg}")
                
                return []
            
            elif response.status_code == 429:
                raise RateLimitException("OpenFIGI rate limit exceeded")
            
            else:
                raise ProviderException(f"OpenFIGI HTTP error {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"OpenFIGI request error: {str(e)}")
    
    def _map_security_type(self, openfigi_type: Optional[str]) -> str:
        """
        Mapea el tipo de seguridad de OpenFIGI a nuestro formato
        
        Args:
            openfigi_type: Tipo de OpenFIGI (ej: 'Common Stock', 'ETF')
            
        Returns:
            Tipo estandarizado ('Stock', 'ETF', 'Bond', etc.)
        """
        if not openfigi_type:
            return 'Stock'  # Default
        
        openfigi_type_lower = openfigi_type.lower()
        
        if 'etf' in openfigi_type_lower or 'exchange traded' in openfigi_type_lower:
            return 'ETF'
        elif 'bond' in openfigi_type_lower or 'note' in openfigi_type_lower:
            return 'Bond'
        elif 'preferred' in openfigi_type_lower:
            return 'Preferred Stock'
        elif 'adr' in openfigi_type_lower or 'gdr' in openfigi_type_lower:
            return 'ADR'
        elif 'right' in openfigi_type_lower or 'warrant' in openfigi_type_lower:
            return 'Derivative'
        else:
            return 'Stock'  # Default para Common Stock y otros

