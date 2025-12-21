"""
Script para poblar MappingRegistry con los mapeos hardcodeados actuales
Ejecutar: python populate_mappings.py
"""
from app import create_app, db
from app.models import MappingRegistry

app = create_app()

# Datos de mapeos actuales (extraídos de los mappers hardcodeados)
MAPPINGS_DATA = {
    'MIC_TO_YAHOO': {
        # ==================
        # US MARKETS
        # ==================
        'XNYS': ('', 'NYSE', 'US'),
        'XNAS': ('', 'NASDAQ', 'US'),
        'ARCX': ('', 'NYSE Arca', 'US'),
        'BATS': ('', 'Cboe BZX (BATS)', 'US'),
        'BATY': ('', 'Cboe BYX', 'US'),
        'CDED': ('', 'Cboe EDGA', 'US'),
        'EDGX': ('', 'Cboe EDGX', 'US'),
        'EDGA': ('', 'Cboe EDGA (alternate)', 'US'),
        'SOHO': ('', 'NYSE National', 'US'),
        'MEMX': ('', 'Members Exchange', 'US'),
        'MSPL': ('', 'Morgan Stanley', 'US'),
        'MSCO': ('', 'Morgan Stanley (alternate)', 'US'),
        'EPRL': ('', 'MIAX Pearl', 'US'),
        'XBOS': ('', 'Nasdaq BX', 'US'),
        'IEXG': ('', 'IEX', 'US'),
        'XCIS': ('', 'NYSE Chicago', 'US'),
        'XPSX': ('', 'Nasdaq PSX', 'US'),
        
        # ==================
        # UK MARKETS
        # ==================
        'XLON': ('.L', 'London Stock Exchange', 'GB'),
        'AIMX': ('.L', 'AIM (London)', 'GB'),
        'JSSI': ('.L', 'LSE (Jersey)', 'GB'),
        'BATE': ('.L', 'Cboe Europe (ex-BATS Europe)', 'GB'),
        'CHIX': ('.L', 'Cboe Europe CXE (ex-CHI-X)', 'GB'),
        'BART': ('.L', 'Barclays MTF', 'GB'),
        'HRSI': ('.L', 'RSX (MTF)', 'GB'),
        
        # ==================
        # EUROPEAN MARKETS
        # ==================
        
        # France
        'XPAR': ('.PA', 'Euronext Paris', 'FR'),
        
        # Germany
        'XETRA': ('.DE', 'XETRA', 'DE'),
        'XETR': ('.DE', 'Deutsche Börse Xetra', 'DE'),  # Alias
        'XETA': ('.DE', 'Frankfurt (alternate)', 'DE'),
        'XETB': ('.DE', 'Frankfurt (Xetra Best Execution)', 'DE'),
        'XETU': ('.DE', 'Frankfurt (Xetra US)', 'DE'),
        'XFRA': ('.F', 'Frankfurt Stock Exchange', 'DE'),
        'FRAA': ('.F', 'Frankfurt (alternate)', 'DE'),
        
        # Spain
        'XMAD': ('.MC', 'Madrid Stock Exchange', 'ES'),
        # NOTA: MESI intencionalmente NO incluido para permitir fallback a exchange
        # Si un asset tiene mic='MESI' pero country='GB', usará exchange='EO' → .L
        'CCEU': ('.MC', 'Continuous Market (Spain)', 'ES'),
        'AQXE': ('.MC', 'Aquis Exchange (Spain)', 'ES'),
        'GROW': ('.MC', 'BME Growth (Spain)', 'ES'),
        'HREU': ('.MC', 'BME Latibex', 'ES'),
        
        # Italy
        'XMIL': ('.MI', 'Borsa Italiana', 'IT'),
        'MTAA': ('.MI', 'MTA (Milan)', 'IT'),
        'CEUO': ('.MI', 'Cboe Europe (Italy)', 'IT'),
        
        # Netherlands
        'XAMS': ('.AS', 'Euronext Amsterdam', 'NL'),
        
        # Sweden
        'XSTO': ('.ST', 'Nasdaq Stockholm', 'SE'),
        
        # Finland
        'XHEL': ('.HE', 'Nasdaq Helsinki', 'FI'),
        'FNSE': ('.HE', 'Helsinki (alternate)', 'FI'),
        
        # Denmark
        'XCSE': ('.CO', 'Nasdaq Copenhagen', 'DK'),
        'DSME': ('.CO', 'Copenhagen (alternate)', 'DK'),
        
        # Norway
        'XOSL': ('.OL', 'Oslo Stock Exchange', 'NO'),
        
        # Poland
        'XWAR': ('.WA', 'Warsaw Stock Exchange', 'PL'),
        
        # Czech Republic
        'XPRA': ('.PR', 'Prague Stock Exchange', 'CZ'),
        
        # Hungary
        'XBUD': ('.BD', 'Budapest Stock Exchange', 'HU'),
        
        # Belgium
        'XBRU': ('.BR', 'Euronext Brussels', 'BE'),
        
        # Portugal
        'XLIS': ('.LS', 'Euronext Lisbon', 'PT'),
        
        # Austria
        'XWBO': ('.VI', 'Vienna Stock Exchange', 'AT'),
        
        # Switzerland
        'XSWX': ('.SW', 'SIX Swiss Exchange', 'CH'),
        
        # ==================
        # PAN-EUROPEAN MTFs
        # ==================
        'AQEU': ('.L', 'Aquis Exchange (default to London)', 'GB'),
        'CEUX': ('.L', 'Cboe Europe (generic)', 'GB'),
        'EUCC': ('.L', 'EuroCCP', 'GB'),
        
        # ==================
        # ASIAN MARKETS
        # ==================
        'XHKG': ('.HK', 'Hong Kong', 'HK'),
        'XJPX': ('.T', 'Tokyo', 'JP'),
        'XSHG': ('.SS', 'Shanghai', 'CN'),
        'XSHE': ('.SZ', 'Shenzhen', 'CN'),
        'XKRX': ('.KS', 'Korea', 'KR'),
        'XTAI': ('.TW', 'Taiwan', 'TW'),
        'XSES': ('.SI', 'Singapore', 'SG'),
        'XTKS': ('.T', 'Tokyo Stock Exchange', 'JP'),  # Alias
        
        # ==================
        # OCEANIA
        # ==================
        'ASXT': ('.AX', 'Australian Securities Exchange', 'AU'),
        'XASX': ('.AX', 'Australian Securities Exchange', 'AU'),  # Alias
        'XNZE': ('.NZ', 'New Zealand', 'NZ'),
        
        # ==================
        # AMERICAS (non-US)
        # ==================
        'XTSE': ('.TO', 'Toronto', 'CA'),
        'XATS': ('.TO', 'TSE Alpha', 'CA'),
        'XCX2': ('.TO', 'TSE (alternate)', 'CA'),
        'XTSX': ('.V', 'TSX Venture', 'CA'),
        'CHIC': ('.V', 'Chi-X Canada', 'CA'),
        'XBOM': ('.BO', 'Bombay', 'IN'),
        'XNSE': ('.NS', 'National Stock Exchange India', 'IN'),
        'XSAU': ('.SA', 'Sao Paulo', 'BR'),
        'BVMF': ('.SA', 'B3 Brazil', 'BR'),  # Alias
        'XMEX': ('.MX', 'Mexico', 'MX'),
        
        # ==================
        # OTHER
        # ==================
        'XGAT': ('', 'Tradegate (Germany) - no Yahoo suffix known', 'DE'),
    },
    
    'EXCHANGE_TO_YAHOO': {
        # US Markets
        'NASDAQ': ('', 'NASDAQ', 'US'),
        'NYSE': ('', 'NYSE', 'US'),
        'ARCA': ('', 'NYSE Arca', 'US'),
        'AMEX': ('', 'NYSE American', 'US'),
        'BATS': ('', 'Cboe BZX', 'US'),
        
        # European Markets
        'LSE': ('.L', 'London', 'GB'),
        'EO': ('.L', 'London Stock Exchange (EO)', 'GB'),  # Mapeo adicional para Volex y similares
        'SBF': ('.PA', 'Paris', 'FR'),
        'IBIS': ('.DE', 'Frankfurt/XETRA', 'DE'),
        'BM': ('.MC', 'Madrid', 'ES'),
        'BVME': ('.MI', 'Milan', 'IT'),
        'AEB': ('.AS', 'Amsterdam', 'NL'),
        'SFB': ('.ST', 'Stockholm', 'SE'),
        'OSE': ('.OL', 'Oslo', 'NO'),
        'CPH': ('.CO', 'Copenhagen', 'DK'),
        'WSE': ('.WA', 'Warsaw', 'PL'),
        'SWX': ('.SW', 'Swiss', 'CH'),
        'VIENNA': ('.VI', 'Vienna', 'AT'),
        'SBEL': ('.BR', 'Brussels', 'BE'),
        'LISBON': ('.LS', 'Lisbon', 'PT'),
        
        # Canadian Markets
        'TSE': ('.TO', 'Toronto', 'CA'),
        'TSXV': ('.V', 'TSX Venture', 'CA'),
        
        # Asian Markets
        'SEHK': ('.HK', 'Hong Kong', 'HK'),
        'SGX': ('.SI', 'Singapore', 'SG'),
        'KSE': ('.KS', 'Korea', 'KR'),
        'TSE.JPN': ('.T', 'Tokyo', 'JP'),
        'HKSE': ('.HK', 'Hong Kong', 'HK'),
        
        # Australian Markets
        'ASX': ('.AX', 'Australia', 'AU'),
        
        # Other Markets
        'BOVESPA': ('.SA', 'Brazil', 'BR'),
        'BMV': ('.MX', 'Mexico', 'MX'),
    },
    
    'DEGIRO_TO_IBKR': {
        # European Exchanges
        'MAD': ('BM', 'Madrid', 'ES'),
        'PAR': ('SBF', 'Paris', 'FR'),
        'FRA': ('IBIS', 'Frankfurt', 'DE'),
        'MIL': ('BVME', 'Milan', 'IT'),
        'AMS': ('AEB', 'Amsterdam', 'NL'),
        'LSE': ('LSE', 'London', 'GB'),
        'STK': ('SFB', 'Stockholm', 'SE'),
        'OSL': ('OSE', 'Oslo', 'NO'),
        'CPH': ('CPH', 'Copenhagen', 'DK'),
        'WAR': ('WSE', 'Warsaw', 'PL'),
        'SWX': ('SWX', 'Swiss', 'CH'),
        'VIE': ('VIENNA', 'Vienna', 'AT'),
        'BRU': ('SBEL', 'Brussels', 'BE'),
        'LIS': ('LISBON', 'Lisbon', 'PT'),
        
        # US Exchanges
        'NDQ': ('NASDAQ', 'NASDAQ', 'US'),
        'NSY': ('NYSE', 'NYSE', 'US'),
        
        # Asian Exchanges
        'HKG': ('SEHK', 'Hong Kong', 'HK'),
        'SGX': ('SGX', 'Singapore', 'SG'),
        'TKS': ('TSE.JPN', 'Tokyo', 'JP'),
        
        # Other
        'ASX': ('ASX', 'Australia', 'AU'),
        'TSE': ('TSE', 'Toronto', 'CA'),
    }
}


def populate_mappings():
    """Poblar MappingRegistry con datos iniciales"""
    
    with app.app_context():
        print("\n" + "="*70)
        print("📊 POBLANDO MAPPINGREGISTRY CON DATOS INICIALES")
        print("="*70 + "\n")
        
        total_created = 0
        total_skipped = 0
        
        for mapping_type, mappings in MAPPINGS_DATA.items():
            print(f"\n🔹 Procesando {mapping_type}:")
            print(f"   Total de mapeos: {len(mappings)}")
            
            created = 0
            skipped = 0
            
            for source_key, (target_value, description, country) in mappings.items():
                # Verificar si ya existe
                existing = MappingRegistry.query.filter_by(
                    mapping_type=mapping_type,
                    source_key=source_key
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                # Crear nuevo mapeo
                mapping = MappingRegistry(
                    mapping_type=mapping_type,
                    source_key=source_key,
                    target_value=target_value,
                    description=description,
                    country=country,
                    created_by='SYSTEM'
                )
                db.session.add(mapping)
                created += 1
            
            db.session.commit()
            
            print(f"   ✅ Creados: {created}")
            print(f"   ⏭️  Omitidos (ya existían): {skipped}")
            
            total_created += created
            total_skipped += skipped
        
        print("\n" + "="*70)
        print("✅ POBLACIÓN COMPLETADA")
        print("="*70)
        print(f"\n📊 Resumen:")
        print(f"   • Total creados: {total_created}")
        print(f"   • Total omitidos: {total_skipped}")
        print(f"   • Total en BD: {MappingRegistry.query.count()}")
        
        # Estadísticas por tipo
        print(f"\n📈 Mapeos por tipo:")
        for mapping_type in ['MIC_TO_YAHOO', 'EXCHANGE_TO_YAHOO', 'DEGIRO_TO_IBKR']:
            count = MappingRegistry.query.filter_by(mapping_type=mapping_type).count()
            print(f"   • {mapping_type}: {count}")
        
        print()


if __name__ == '__main__':
    populate_mappings()

