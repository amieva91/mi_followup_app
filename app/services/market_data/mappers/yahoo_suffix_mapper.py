"""
Mapeo de MIC ISO 10383 a sufijo de Yahoo Finance
"""

class YahooSuffixMapper:
    """
    Mapea códigos MIC (Market Identifier Code) ISO 10383 a sufijos de Yahoo Finance
    """
    
    # MIC ISO 10383 → Yahoo Finance suffix
    MIC_TO_YAHOO_SUFFIX = {
        # ==================
        # US MARKETS
        # ==================
        'XNYS': '',     # NYSE
        'XNAS': '',     # NASDAQ
        'ARCX': '',     # NYSE Arca
        'BATS': '',     # Cboe BZX (BATS)
        'BATY': '',     # Cboe BYX
        'CDED': '',     # Cboe EDGA
        'EDGX': '',     # Cboe EDGX
        'EDGA': '',     # Cboe EDGA (alternate)
        'SOHO': '',     # NYSE National
        'MEMX': '',     # Members Exchange
        'MSPL': '',     # Morgan Stanley
        'MSCO': '',     # Morgan Stanley (alternate)
        'EPRL': '',     # MIAX Pearl
        'XBOS': '',     # Nasdaq BX
        'IEXG': '',     # IEX
        'XCIS': '',     # NYSE Chicago
        'XPSX': '',     # Nasdaq PSX
        
        # ==================
        # UK MARKETS
        # ==================
        'XLON': '.L',   # London Stock Exchange
        'AIMX': '.L',   # AIM (London)
        'JSSI': '.L',   # LSE (Jersey)
        'BATE': '.L',   # Cboe Europe (ex-BATS Europe)
        'CHIX': '.L',   # Cboe Europe CXE (ex-CHI-X)
        'BART': '.L',   # Barclays MTF
        'HRSI': '.L',   # RSX (MTF)
        
        # ==================
        # EUROPEAN MARKETS
        # ==================
        
        # France
        'XPAR': '.PA',  # Euronext Paris
        
        # Germany
        'XETRA': '.DE', # XETRA
        'XETA': '.DE',  # Frankfurt (alternate)
        'XETB': '.DE',  # Frankfurt (Xetra Best Execution)
        'XETU': '.DE',  # Frankfurt (Xetra US)
        'XFRA': '.F',   # Frankfurt Stock Exchange
        'FRAA': '.F',   # Frankfurt (alternate)
        
        # Spain
        'XMAD': '.MC',  # Madrid Stock Exchange
        'MESI': '.MC',  # SIBE (Madrid electronic)
        'CCEU': '.MC',  # Continuous Market (Spain)
        'AQXE': '.MC',  # Aquis Exchange (Spain)
        'GROW': '.MC',  # BME Growth (Spain)
        'HREU': '.MC',  # BME Latibex
        
        # Italy
        'XMIL': '.MI',  # Borsa Italiana
        'MTAA': '.MI',  # MTA (Milan)
        'CEUO': '.MI',  # Cboe Europe (Italy)
        
        # Netherlands
        'XAMS': '.AS',  # Euronext Amsterdam
        
        # Sweden
        'XSTO': '.ST',  # Nasdaq Stockholm
        
        # Finland
        'XHEL': '.HE',  # Nasdaq Helsinki
        'FNSE': '.HE',  # Helsinki (alternate)
        
        # Denmark
        'XCSE': '.CO',  # Nasdaq Copenhagen
        'DSME': '.CO',  # Copenhagen (alternate)
        
        # Norway
        'XOSL': '.OL',  # Oslo Stock Exchange
        
        # Poland
        'XWAR': '.WA',  # Warsaw Stock Exchange
        
        # Czech Republic
        'XPRA': '.PR',  # Prague Stock Exchange
        
        # Hungary
        'XBUD': '.BD',  # Budapest Stock Exchange
        
        # Belgium
        'XBRU': '.BR',  # Euronext Brussels
        
        # Portugal
        'XLIS': '.LS',  # Euronext Lisbon
        
        # Austria
        'XWBO': '.VI',  # Vienna Stock Exchange
        
        # Switzerland
        'XSWX': '.SW',  # SIX Swiss Exchange
        
        # ==================
        # PAN-EUROPEAN MTFs
        # ==================
        'AQEU': '.L',   # Aquis Exchange (default to London)
        'CEUX': '.L',   # Cboe Europe (generic)
        'EUCC': '.L',   # EuroCCP
        
        # ==================
        # ASIAN MARKETS
        # ==================
        'XHKG': '.HK',  # Hong Kong
        'XJPX': '.T',   # Tokyo
        'XSHG': '.SS',  # Shanghai
        'XSHE': '.SZ',  # Shenzhen
        'XKRX': '.KS',  # Korea
        'XTAI': '.TW',  # Taiwan
        'XSES': '.SI',  # Singapore
        
        # ==================
        # OCEANIA
        # ==================
        'ASXT': '.AX',  # Australian Securities Exchange
        'XNZE': '.NZ',  # New Zealand
        
        # ==================
        # AMERICAS (non-US)
        # ==================
        'XTSE': '.TO',  # Toronto
        'XATS': '.TO',  # TSE Alpha
        'XCX2': '.TO',  # TSE (alternate)
        'XTSX': '.V',   # TSX Venture
        'CHIC': '.V',   # Chi-X Canada
        'XBOM': '.BO',  # Bombay
        'XNSE': '.NS',  # National Stock Exchange India
        'XSAU': '.SA',  # Sao Paulo
        'XMEX': '.MX',  # Mexico
        
        # ==================
        # OTHER
        # ==================
        'XGAT': '',     # Tradegate (Germany) - no Yahoo suffix known
    }
    
    # Sufijos Yahoo Finance → nombre del mercado
    SUFFIX_NAMES = {
        '': 'United States',
        '.L': 'London',
        '.PA': 'Paris',
        '.DE': 'Germany (XETRA)',
        '.F': 'Frankfurt',
        '.MC': 'Madrid',
        '.MI': 'Milan',
        '.AS': 'Amsterdam',
        '.ST': 'Stockholm',
        '.HE': 'Helsinki',
        '.CO': 'Copenhagen',
        '.OL': 'Oslo',
        '.WA': 'Warsaw',
        '.PR': 'Prague',
        '.BD': 'Budapest',
        '.BR': 'Brussels',
        '.LS': 'Lisbon',
        '.VI': 'Vienna',
        '.SW': 'Switzerland',
        '.HK': 'Hong Kong',
        '.T': 'Tokyo',
        '.SS': 'Shanghai',
        '.SZ': 'Shenzhen',
        '.KS': 'Korea',
        '.TW': 'Taiwan',
        '.SI': 'Singapore',
        '.AX': 'Australia',
        '.NZ': 'New Zealand',
        '.TO': 'Toronto',
        '.V': 'TSX Venture',
        '.BO': 'Bombay',
        '.NS': 'India NSE',
        '.SA': 'Sao Paulo',
        '.MX': 'Mexico',
    }
    
    @classmethod
    def mic_to_yahoo_suffix(cls, mic: str) -> str:
        """
        Convierte un MIC ISO 10383 al sufijo de Yahoo Finance
        LEE DESDE BASE DE DATOS (MappingRegistry)
        
        Args:
            mic: Código MIC (ej: 'XMAD', 'XLON')
            
        Returns:
            Sufijo Yahoo (ej: '.MC', '.L')
        """
        if not mic:
            return ''
        
        # Leer desde BD (MappingRegistry)
        from app.models import MappingRegistry
        result = MappingRegistry.get_mapping('MIC_TO_YAHOO', mic)
        return result if result is not None else ''
    
    @classmethod
    def get_market_name(cls, suffix: str) -> str:
        """
        Obtiene el nombre del mercado a partir del sufijo
        
        Args:
            suffix: Sufijo Yahoo (ej: '.MC')
            
        Returns:
            Nombre del mercado (ej: 'Madrid')
        """
        return cls.SUFFIX_NAMES.get(suffix, 'Unknown')
    
    @classmethod
    def get_all_mics(cls):
        """Retorna todos los MICs soportados"""
        return list(cls.MIC_TO_YAHOO_SUFFIX.keys())
    
    @classmethod
    def get_all_suffixes(cls):
        """Retorna todos los sufijos únicos soportados"""
        return list(set(cls.MIC_TO_YAHOO_SUFFIX.values()))
    
    # Mapeo de Exchange (IBKR/unificado) a Yahoo Suffix
    # Fallback cuando no hay MIC disponible
    EXCHANGE_TO_YAHOO_SUFFIX = {
        # US Markets
        'NASDAQ': '',
        'NYSE': '',
        'ARCA': '',
        'AMEX': '',
        'BATS': '',
        
        # European Markets
        'LSE': '.L',        # London
        'SBF': '.PA',       # Paris
        'IBIS': '.DE',      # Frankfurt/XETRA
        'BM': '.MC',        # Madrid
        'BVME': '.MI',      # Milan
        'AEB': '.AS',       # Amsterdam
        'SFB': '.ST',       # Stockholm
        'OSE': '.OL',       # Oslo
        'CPH': '.CO',       # Copenhagen
        'WSE': '.WA',       # Warsaw
        'SWX': '.SW',       # Swiss
        'VIENNA': '.VI',    # Vienna
        'SBEL': '.BR',      # Brussels
        'LISBON': '.LS',    # Lisbon
        
        # Canadian Markets
        'TSE': '.TO',       # Toronto
        'TSXV': '.V',       # TSX Venture
        
        # Asian Markets
        'SEHK': '.HK',      # Hong Kong
        'SGX': '.SI',       # Singapore
        'KSE': '.KS',       # Korea
        'TSE.JPN': '.T',    # Tokyo
        'HKSE': '.HK',      # Hong Kong (alternate)
        
        # Australian Markets
        'ASX': '.AX',       # Australia
        
        # Other Markets
        'BOVESPA': '.SA',   # Brazil
        'BMV': '.MX',       # Mexico
    }
    
    @classmethod
    def exchange_to_yahoo_suffix(cls, exchange: str) -> str:
        """
        Mapea código de exchange (IBKR unificado) a sufijo de Yahoo Finance
        Fallback cuando no hay MIC disponible
        LEE DESDE BASE DE DATOS (MappingRegistry)
        
        Args:
            exchange: Código de exchange (ej: 'NASDAQ', 'BM', 'LSE')
            
        Returns:
            Sufijo de Yahoo Finance (ej: '', '.MC', '.L')
            None si el exchange no se encuentra en el mapeo
        """
        if not exchange:
            return None
        
        # Leer desde BD (MappingRegistry)
        from app.models import MappingRegistry
        return MappingRegistry.get_mapping('EXCHANGE_TO_YAHOO', exchange)

