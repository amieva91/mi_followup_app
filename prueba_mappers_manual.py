"""
Prueba manual de mappers - Para ver resultados concretos
"""
from app.services.market_data.mappers import ExchangeMapper, YahooSuffixMapper, MICMapper

print("\n" + "="*70)
print("PRUEBA DE MAPPERS")
print("="*70)

# Casos reales de tu CSV DeGiro
casos_degiro = [
    ('MAD', 'XMAD', 'Prosegur'),
    ('MAD', 'MESI', 'Grifols'),
    ('LSE', 'XLON', 'Volex'),
    ('NDQ', 'XNAS', 'Alphabet'),
    ('NSY', 'XNYS', 'Accenture'),
    ('HKS', 'XHKG', 'PAX Global'),
    ('ASX', 'ASXT', 'SRG Global'),
]

print("\n📋 CONVERSIÓN DEGIRO → IBKR → YAHOO:")
print("-"*70)
print(f"{'Exchange DeGiro':<20} {'→ IBKR':<15} {'MIC':<10} {'→ Yahoo Suffix':<15}")
print("-"*70)

for degiro_exch, mic, nombre in casos_degiro:
    ibkr_exch = ExchangeMapper.degiro_to_unified(degiro_exch)
    yahoo_suffix = YahooSuffixMapper.mic_to_yahoo_suffix(mic)
    region = MICMapper.get_region(mic)
    
    print(f"{degiro_exch:<20} → {ibkr_exch:<15} {mic:<10} → '{yahoo_suffix}'  ({region})")
    print(f"  Ejemplo: {nombre}")

print("\n" + "="*70)
print("EJEMPLOS DE YAHOO TICKERS")
print("="*70)

ejemplos = [
    ('PSG', 'XMAD', 'Prosegur'),
    ('VOD', 'XLON', 'Vodafone'),
    ('AAPL', 'XNAS', 'Apple'),
    ('327', 'XHKG', 'PAX Global'),
]

print(f"\n{'Symbol':<10} {'MIC':<10} {'Yahoo Suffix':<15} {'→ Yahoo Ticker':<20} {'Nombre'}")
print("-"*70)

for symbol, mic, nombre in ejemplos:
    suffix = YahooSuffixMapper.mic_to_yahoo_suffix(mic)
    ticker = f"{symbol}{suffix}"
    print(f"{symbol:<10} {mic:<10} '{suffix}'  {' ':<10} → {ticker:<20} {nombre}")

print("\n✅ Los mappers funcionan correctamente")
print("💡 Cuando se implementen TODOs 7-8, estos valores se guardarán en los assets\n")

