"""
Helper para manejo de códigos MIC ISO 10383
"""

class MICMapper:
    """
    Utilidades para trabajar con Market Identifier Codes (MIC) ISO 10383
    """
    
    # MICs principales por región (Operating MICs)
    PRIMARY_MICS = {
        'XNYS', 'XNAS', 'XLON', 'XPAR', 'XETRA', 'XMAD', 'XMIL', 
        'XAMS', 'XSTO', 'XHEL', 'XCSE', 'XOSL', 'XWAR', 'XHKG',
        'XJPX', 'XSHG', 'XSHE', 'XKRX', 'ASXT', 'XTSE', 'XBOM',
    }
    
    # MTFs y segmentos relacionados con sus MICs principales
    MTF_TO_PRIMARY = {
        # US alternative venues → NASDAQ/NYSE
        'ARCX': 'XNYS',
        'BATS': 'XNAS',
        'BATY': 'XNAS',
        'CDED': 'XNAS',
        'EDGX': 'XNAS',
        'EDGA': 'XNAS',
        'SOHO': 'XNYS',
        'MEMX': 'XNAS',
        'MSPL': 'XNAS',
        'MSCO': 'XNAS',
        'EPRL': 'XNAS',
        'XBOS': 'XNAS',
        'IEXG': 'XNAS',
        'XCIS': 'XNYS',
        'XPSX': 'XNAS',
        
        # UK MTFs → London
        'AIMX': 'XLON',
        'JSSI': 'XLON',
        'BATE': 'XLON',
        'CHIX': 'XLON',
        'BART': 'XLON',
        'HRSI': 'XLON',
        
        # Frankfurt variants → XETRA
        'XETA': 'XETRA',
        'XETB': 'XETRA',
        'XETU': 'XETRA',
        'XFRA': 'XETRA',
        'FRAA': 'XETRA',
        
        # Madrid segments → Madrid
        'MESI': 'XMAD',
        'CCEU': 'XMAD',
        'AQXE': 'XMAD',
        'GROW': 'XMAD',
        'HREU': 'XMAD',
        
        # Milan segments → Milan
        'MTAA': 'XMIL',
        'CEUO': 'XMIL',
        
        # Helsinki variants
        'FNSE': 'XHEL',
        
        # Copenhagen variants
        'DSME': 'XCSE',
        
        # Toronto variants
        'XATS': 'XTSE',
        'XCX2': 'XTSE',
        
        # TSX Venture variants
        'CHIC': 'XTSX',
        
        # Pan-European MTFs (default to London)
        'AQEU': 'XLON',
        'CEUX': 'XLON',
        'EUCC': 'XLON',
    }
    
    @classmethod
    def is_primary_mic(cls, mic: str) -> bool:
        """
        Verifica si un MIC es principal (Operating MIC)
        
        Args:
            mic: Código MIC
            
        Returns:
            True si es un MIC principal
        """
        return mic in cls.PRIMARY_MICS
    
    @classmethod
    def get_primary_mic(cls, mic: str) -> str:
        """
        Obtiene el MIC principal asociado a un MIC/MTF
        
        Args:
            mic: Código MIC o MTF
            
        Returns:
            MIC principal (o el mismo si ya es principal)
        """
        if cls.is_primary_mic(mic):
            return mic
        return cls.MTF_TO_PRIMARY.get(mic, mic)
    
    @classmethod
    def is_us_market(cls, mic: str) -> bool:
        """Verifica si un MIC es de mercados US"""
        us_mics = {
            'XNYS', 'XNAS', 'ARCX', 'BATS', 'BATY', 'CDED', 'EDGX', 'EDGA',
            'SOHO', 'MEMX', 'MSPL', 'MSCO', 'EPRL', 'XBOS', 'IEXG', 'XCIS', 'XPSX'
        }
        return mic in us_mics
    
    @classmethod
    def get_region(cls, mic: str) -> str:
        """
        Obtiene la región de un MIC
        
        Returns:
            'US', 'EU', 'UK', 'ASIA', 'OTHER'
        """
        if cls.is_us_market(mic):
            return 'US'
        
        uk_mics = {'XLON', 'AIMX', 'JSSI', 'BATE', 'CHIX', 'BART', 'HRSI'}
        if mic in uk_mics:
            return 'UK'
        
        eu_mics = {
            'XPAR', 'XETRA', 'XETA', 'XETB', 'XETU', 'XFRA', 'FRAA',
            'XMAD', 'MESI', 'CCEU', 'AQXE', 'GROW', 'HREU',
            'XMIL', 'MTAA', 'CEUO', 'XAMS', 'XSTO', 'XHEL', 'FNSE',
            'XCSE', 'DSME', 'XOSL', 'XWAR', 'XPRA', 'XBUD', 'XBRU',
            'XLIS', 'XWBO', 'XSWX', 'AQEU', 'CEUX', 'EUCC'
        }
        if mic in eu_mics:
            return 'EU'
        
        asia_mics = {'XHKG', 'XJPX', 'XSHG', 'XSHE', 'XKRX', 'XTAI', 'XSES'}
        if mic in asia_mics:
            return 'ASIA'
        
        return 'OTHER'

