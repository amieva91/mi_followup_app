"""
Analiza todos los CSVs para extraer códigos únicos de exchange
y crear los mapeos necesarios
"""
import csv
from collections import defaultdict

print("\n" + "="*80)
print("ANÁLISIS DE EXCHANGES EN CSVs")
print("="*80)

# ========================================
# 1. ANALIZAR DEGIRO
# ========================================
print("\n📊 ANALIZANDO DEGIRO (TransaccionesDegiro.csv)...")

degiro_exchanges = defaultdict(set)  # {col4_value: set(col5_mic_values)}
degiro_mics = set()

try:
    with open('uploads/TransaccionesDegiro.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        
        for row in reader:
            if len(row) > 5:
                col4 = row[4].strip()  # Bolsa de
                col5 = row[5].strip()  # Centro de (MIC)
                producto = row[2].strip()
                
                if col4 and col5:
                    degiro_exchanges[col4].add((col5, producto))
                    degiro_mics.add(col5)
    
    print(f"✅ DeGiro - Columna 4 (Bolsa de) valores únicos: {len(degiro_exchanges)}")
    print(f"✅ DeGiro - Columna 5 (MIC) valores únicos: {len(degiro_mics)}")
    
    print("\n📋 DETALLE DE EXCHANGES DEGIRO:")
    for col4, mics_prods in sorted(degiro_exchanges.items()):
        mics = sorted(set(mic for mic, _ in mics_prods))
        print(f"   {col4:30s} → MICs: {', '.join(mics)}")
        # Mostrar un ejemplo de producto
        ejemplo = list(mics_prods)[0][1]
        print(f"      Ejemplo: {ejemplo[:50]}")

except FileNotFoundError:
    print("⚠️  Archivo TransaccionesDegiro.csv no encontrado")

# ========================================
# 2. ANALIZAR IBKR
# ========================================
print("\n📊 ANALIZANDO IBKR...")

ibkr_exchanges = set()
ibkr_files = [
    'uploads/IBKR.csv',
    'uploads/IBKR1.csv',
    'uploads/IBKR2.csv'
]

for file_path in ibkr_files:
    try:
        print(f"\n   Procesando {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            in_instruments = False
            
            for line in f:
                line = line.strip()
                
                if 'Información de instrumento financiero' in line or 'Financial Instrument Information' in line:
                    in_instruments = True
                    continue
                
                if in_instruments:
                    if line.startswith('Operaciones') or line.startswith('Trades'):
                        break
                    
                    if line and not line.startswith('Información') and not line.startswith('Financial'):
                        parts = line.split(',')
                        if len(parts) >= 8:
                            # Buscar la columna "Merc. de cotización" o "Listing Exch"
                            # Está en diferentes posiciones dependiendo del formato
                            for i, part in enumerate(parts):
                                part = part.strip().strip('"')
                                # Si parece un código de exchange (2-4 letras mayúsculas)
                                if part and len(part) <= 4 and part.isupper() and part.isalpha():
                                    if part not in ['ISIN', 'USD', 'EUR', 'GBP', 'CAD', 'ETF', 'STK']:
                                        ibkr_exchanges.add(part)
        
        print(f"   ✅ Procesado {file_path}")
    
    except FileNotFoundError:
        print(f"   ⚠️  {file_path} no encontrado")

print(f"\n✅ IBKR - Exchanges únicos encontrados: {len(ibkr_exchanges)}")
print(f"   {sorted(ibkr_exchanges)}")

# ========================================
# 3. GENERAR MAPEO UNIFICADO
# ========================================
print("\n" + "="*80)
print("PROPUESTA DE MAPEO UNIFICADO")
print("="*80)

# Mapeo manual basado en conocimiento de mercados
unified_mapping = {
    # DeGiro col4 → Código IBKR equivalente
    'NSY': 'NYSE',
    'NDQ': 'NASDAQ',
    'LSE': 'LSE',
    'EPA': 'SBF',  # Euronext Paris
    'FRA': 'IBIS',  # Frankfurt
    'BIT': 'BVME',  # Borsa Italiana / Milan
    'AMS': 'AEB',   # Amsterdam
    'BME': 'BM',    # Madrid
    'STO': 'SFB',   # Stockholm
    'OSL': 'OSE',   # Oslo
    'HEL': 'HEX',   # Helsinki
    'CPH': 'CPH',   # Copenhagen
    'WAR': 'WSE',   # Warsaw
    'BRU': 'BELFOX', # Brussels
    'LIS': 'BVLP',  # Lisbon
    'VIE': 'VSE',   # Vienna
    'PRA': 'PSE',   # Prague
    'BUD': 'BUX',   # Budapest
    'HKG': 'SEHK',  # Hong Kong
    'TSE': 'TSE',   # Tokyo
    'ASX': 'ASX',   # Australian
    'NZE': 'NZSE',  # New Zealand
    'TOR': 'TSE',   # Toronto (Canada)
}

print("\n📋 MAPEO DEGIRO COL4 → IBKR EXCHANGE:")
for degiro_col4 in sorted(degiro_exchanges.keys()):
    ibkr_equiv = unified_mapping.get(degiro_col4, f"UNKNOWN_{degiro_col4}")
    mics = sorted(set(mic for mic, _ in degiro_exchanges[degiro_col4]))
    print(f"   '{degiro_col4}': '{ibkr_equiv}',  # MICs: {', '.join(mics[:3])}")

# ========================================
# 4. GENERAR MAPEO YAHOO SUFFIX
# ========================================
print("\n📋 MAPEO MIC ISO 10383 → YAHOO SUFFIX:")

yahoo_suffix_mapping = {
    # US markets
    'XNYS': '',     # NYSE
    'XNAS': '',     # NASDAQ
    'ARCX': '',     # NYSE Arca
    'BATS': '',     # BATS
    'CDED': '',     # CboeBYX
    'SOHO': '',     # NYSE National
    'MEMX': '',     # MEMX
    'MSPL': '',     # Morgan Stanley
    'EDGX': '',     # Cboe EDGX
    'EPRL': '',     # Miax Pearl
    'XBOS': '',     # Nasdaq BX
    'IEXG': '',     # IEX
    
    # European markets
    'XLON': '.L',   # London
    'AIMX': '.L',   # AIM London
    'XPAR': '.PA',  # Paris
    'XETRA': '.DE', # XETRA
    'XETA': '.DE',  # Frankfurt
    'XFRA': '.F',   # Frankfurt
    'XMAD': '.MC',  # Madrid
    'MESI': '.MC',  # Madrid (SIBE)
    'CCEU': '.MC',  # Continuous Market (Spain)
    'XMIL': '.MI',  # Milan
    'MTAA': '.MI',  # Milan (MTA)
    'XAMS': '.AS',  # Amsterdam
    'XSTO': '.ST',  # Stockholm
    'XHEL': '.HE',  # Helsinki
    'XCSE': '.CO',  # Copenhagen
    'XOSL': '.OL',  # Oslo
    'XWAR': '.WA',  # Warsaw
    'XPRA': '.PR',  # Prague
    'XBUD': '.BD',  # Budapest
    'XBRU': '.BR',  # Brussels
    'XLIS': '.LS',  # Lisbon
    'XWBO': '.VI',  # Vienna
    'XSWX': '.SW',  # Swiss
    
    # Asian markets
    'XHKG': '.HK',  # Hong Kong
    'XJPX': '.T',   # Tokyo
    'XSHG': '.SS',  # Shanghai
    'XSHE': '.SZ',  # Shenzhen
    'XKRX': '.KS',  # Korea
    'XTAI': '.TW',  # Taiwan
    'XSES': '.SI',  # Singapore
    
    # Oceania
    'ASXT': '.AX',  # Australian
    'XNZE': '.NZ',  # New Zealand
    
    # Americas
    'XTSE': '.TO',  # Toronto
    'XTSX': '.V',   # TSX Venture
    'XBOM': '.BO',  # Bombay
    'XNSE': '.NS',  # National Stock Exchange India
    'XSAU': '.SA',  # Sao Paulo
    'XMEX': '.MX',  # Mexico
    
    # UK regional
    'JSSI': '.L',   # LSE (Jersey)
}

mics_with_suffix = sorted([mic for mic in degiro_mics if mic in yahoo_suffix_mapping])
mics_without_suffix = sorted([mic for mic in degiro_mics if mic not in yahoo_suffix_mapping])

print(f"\n✅ MICs con mapeo a Yahoo: {len(mics_with_suffix)}/{len(degiro_mics)}")
for mic in mics_with_suffix:
    suffix = yahoo_suffix_mapping[mic]
    print(f"   '{mic}': '{suffix}',")

if mics_without_suffix:
    print(f"\n⚠️  MICs sin mapeo a Yahoo ({len(mics_without_suffix)}):")
    for mic in mics_without_suffix:
        print(f"   '{mic}': '',  # TODO: Determinar sufijo correcto")

print("\n" + "="*80)
print("RESUMEN")
print("="*80)
print(f"""
✅ DeGiro Exchanges (col4): {len(degiro_exchanges)} únicos
✅ DeGiro MICs (col5): {len(degiro_mics)} únicos
✅ IBKR Exchanges: {len(ibkr_exchanges)} únicos
✅ Mapeo Yahoo Suffix: {len(mics_with_suffix)}/{len(degiro_mics)} MICs cubiertos

📝 SIGUIENTES PASOS:
   1. Crear exchange_mapper.py con mapeo DeGiro col4 → IBKR
   2. Crear yahoo_suffix_mapper.py con mapeo MIC → Yahoo suffix
   3. Implementar enriquecimiento automático con OpenFIGI
""")
print()

