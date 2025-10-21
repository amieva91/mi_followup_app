"""
Servicio de enriquecimiento de assets
Orquesta el uso de providers y mappers para completar datos de assets
"""
from typing import Optional, Dict
from ..providers.openfigi import OpenFIGIProvider
from ..mappers.exchange_mapper import ExchangeMapper
from ..mappers.yahoo_suffix_mapper import YahooSuffixMapper
from ..mappers.mic_mapper import MICMapper
from ..exceptions import EnrichmentException

class AssetEnricher:
    """
    Servicio para enriquecer assets con datos externos
    Usa OpenFIGI como fuente principal y aplica mapeos
    """
    
    def __init__(self, openfigi_api_key: Optional[str] = None):
        """
        Args:
            openfigi_api_key: API key opcional para OpenFIGI
        """
        self.openfigi = OpenFIGIProvider(api_key=openfigi_api_key)
        self.exchange_mapper = ExchangeMapper
        self.yahoo_suffix_mapper = YahooSuffixMapper
        self.mic_mapper = MICMapper
    
    def enrich_from_isin(
        self,
        isin: str,
        currency: str,
        degiro_exchange: Optional[str] = None,
        degiro_mic: Optional[str] = None
    ) -> Dict:
        """
        Enriquece un asset usando ISIN y datos de DeGiro
        
        Args:
            isin: Código ISIN
            currency: Moneda del asset
            degiro_exchange: Código de exchange de DeGiro (columna 4)
            degiro_mic: Código MIC de DeGiro (columna 5)
            
        Returns:
            Dict con todos los datos enriquecidos
        """
        result = {
            'symbol': None,
            'name': None,
            'exchange': None,
            'mic': None,
            'yahoo_suffix': None,
            'currency': currency,
            'asset_type': 'Stock',
            'source': None,
        }
        
        # 1. Si tenemos MIC de DeGiro, usarlo directamente y generar suffix
        if degiro_mic:
            result['mic'] = degiro_mic
            result['yahoo_suffix'] = self.yahoo_suffix_mapper.mic_to_yahoo_suffix(degiro_mic)
        
        # 2. Si tenemos exchange de DeGiro, convertirlo a formato unificado
        if degiro_exchange:
            result['exchange'] = self.exchange_mapper.degiro_to_unified(degiro_exchange)
        
        # 3. Enriquecer con OpenFIGI (obtener symbol, name, asset_type)
        try:
            openfigi_data = self.openfigi.enrich_by_isin(isin, currency)
            
            if openfigi_data:
                # OpenFIGI prevalece para symbol, name, asset_type
                result['symbol'] = openfigi_data.get('symbol')
                result['name'] = openfigi_data.get('name')
                result['asset_type'] = openfigi_data.get('asset_type', 'Stock')
                result['source'] = 'OpenFIGI'
                
                # Si OpenFIGI tiene MIC, prevalece sobre el de DeGiro
                if openfigi_data.get('mic'):
                    result['mic'] = openfigi_data['mic']
                    result['yahoo_suffix'] = self.yahoo_suffix_mapper.mic_to_yahoo_suffix(openfigi_data['mic'])
                
                # Si no teníamos exchange, usar el de OpenFIGI
                if not result['exchange'] and openfigi_data.get('exchange'):
                    result['exchange'] = openfigi_data['exchange']
            else:
                result['source'] = 'Manual'
        
        except Exception as e:
            # Si falla OpenFIGI, continuamos con los datos que tenemos
            result['source'] = 'Partial'
            print(f"Warning: Failed to enrich {isin} with OpenFIGI: {str(e)}")
        
        # 4. Si aún no tenemos yahoo_suffix pero tenemos MIC, generarlo
        if not result['yahoo_suffix'] and result['mic']:
            result['yahoo_suffix'] = self.yahoo_suffix_mapper.mic_to_yahoo_suffix(result['mic'])
        
        return result
    
    def enrich_from_symbol(
        self,
        symbol: str,
        exchange: Optional[str] = None,
        mic: Optional[str] = None
    ) -> Dict:
        """
        Enriquece un asset usando símbolo (típicamente IBKR)
        
        Args:
            symbol: Símbolo del asset
            exchange: Exchange unificado (opcional)
            mic: MIC ISO 10383 (opcional)
            
        Returns:
            Dict con todos los datos enriquecidos
        """
        result = {
            'symbol': symbol,
            'name': None,
            'exchange': exchange,
            'mic': mic,
            'yahoo_suffix': None,
            'currency': None,
            'asset_type': 'Stock',
            'source': None,
        }
        
        # 1. Si tenemos MIC, generar yahoo_suffix
        if mic:
            result['yahoo_suffix'] = self.yahoo_suffix_mapper.mic_to_yahoo_suffix(mic)
        
        # 2. Enriquecer con OpenFIGI (obtener ISIN, name, etc.)
        try:
            openfigi_data = self.openfigi.enrich_by_symbol(symbol, exchange)
            
            if openfigi_data:
                result['name'] = openfigi_data.get('name')
                result['currency'] = openfigi_data.get('currency')
                result['asset_type'] = openfigi_data.get('asset_type', 'Stock')
                result['source'] = 'OpenFIGI'
                
                # Si OpenFIGI tiene MIC, prevalece
                if openfigi_data.get('mic'):
                    result['mic'] = openfigi_data['mic']
                    result['yahoo_suffix'] = self.yahoo_suffix_mapper.mic_to_yahoo_suffix(openfigi_data['mic'])
                
                # Actualizar exchange si OpenFIGI lo proporciona
                if openfigi_data.get('exchange'):
                    result['exchange'] = openfigi_data['exchange']
            else:
                result['source'] = 'Manual'
        
        except Exception as e:
            result['source'] = 'Partial'
            print(f"Warning: Failed to enrich {symbol} with OpenFIGI: {str(e)}")
        
        return result
    
    def update_from_yahoo_url(self, url: str) -> Optional[Dict]:
        """
        Extrae symbol y suffix de una URL de Yahoo Finance
        
        Args:
            url: URL de Yahoo Finance (ej: https://es.finance.yahoo.com/quote/PSG.MC/)
            
        Returns:
            Dict con symbol, suffix (yahoo_suffix) y full_ticker o None si URL inválida
        """
        # Importar aquí para evitar dependencia circular
        from ..providers.yahoo_finance import YahooFinanceProvider
        
        yahoo = YahooFinanceProvider()
        parsed = yahoo.parse_yahoo_url(url)
        
        if not parsed:
            return None
        
        return parsed  # Ya contiene 'symbol', 'suffix', 'full_ticker'

