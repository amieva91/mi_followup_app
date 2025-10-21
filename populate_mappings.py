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
        # US Markets
        'XNYS': ('', 'NYSE', 'US'),
        'XNAS': ('', 'NASDAQ', 'US'),
        'ARCX': ('', 'NYSE Arca', 'US'),
        'BATS': ('', 'Cboe BZX', 'US'),
        
        # UK Markets
        'XLON': ('.L', 'London Stock Exchange', 'GB'),
        'AIMX': ('.L', 'AIM London', 'GB'),
        
        # European Markets
        'XMAD': ('.MC', 'Bolsa de Madrid', 'ES'),
        'XPAR': ('.PA', 'Euronext Paris', 'FR'),
        'XETR': ('.DE', 'Deutsche Börse Xetra', 'DE'),
        'XMIL': ('.MI', 'Borsa Italiana', 'IT'),
        'XAMS': ('.AS', 'Euronext Amsterdam', 'NL'),
        'XSTO': ('.ST', 'Nasdaq Stockholm', 'SE'),
        'XOSL': ('.OL', 'Oslo Børs', 'NO'),
        'XCSE': ('.CO', 'Nasdaq Copenhagen', 'DK'),
        'XWAR': ('.WA', 'Warsaw Stock Exchange', 'PL'),
        'XSWX': ('.SW', 'SIX Swiss Exchange', 'CH'),
        'XWBO': ('.VI', 'Wiener Börse', 'AT'),
        'XBRU': ('.BR', 'Euronext Brussels', 'BE'),
        'XLIS': ('.LS', 'Euronext Lisbon', 'PT'),
        
        # Canadian Markets
        'XTSE': ('.TO', 'Toronto Stock Exchange', 'CA'),
        'XTSX': ('.V', 'TSX Venture Exchange', 'CA'),
        
        # Asian Markets
        'XHKG': ('.HK', 'Hong Kong Stock Exchange', 'HK'),
        'XSES': ('.SI', 'Singapore Exchange', 'SG'),
        'XKRX': ('.KS', 'Korea Exchange', 'KR'),
        'XTKS': ('.T', 'Tokyo Stock Exchange', 'JP'),
        
        # Australian Markets
        'XASX': ('.AX', 'Australian Securities Exchange', 'AU'),
        
        # Other Markets
        'BVMF': ('.SA', 'B3 Brazil', 'BR'),
        'XMEX': ('.MX', 'Bolsa Mexicana', 'MX'),
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

