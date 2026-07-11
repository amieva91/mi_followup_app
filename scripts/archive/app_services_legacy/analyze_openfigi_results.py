"""
Análisis de resultados de OpenFIGI
Muestra solo los resultados más relevantes (exchange principal)
"""
import requests
import json

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Mapeo de monedas a exchanges principales (MIC codes)
CURRENCY_TO_PRIMARY_EXCHANGE = {
    'EUR': ['XMAD', 'XPAR', 'XETR', 'XAMS', 'XMIL', 'XLIS'],  # España, Francia, Alemania, etc.
    'USD': ['XNYS', 'XNAS', 'ARCX'],  # NYSE, NASDAQ, NYSE Arca
    'GBP': ['XLON'],  # London Stock Exchange
    'GBX': ['XLON'],  # London (pence)
    'HKD': ['XHKG'],  # Hong Kong Exchange
    'PLN': ['XWAR'],  # Warsaw Stock Exchange
    'SEK': ['XSTO'],  # Stockholm
    'NOK': ['XOSL'],  # Oslo
    'CAD': ['XTSE', 'XTSX'],  # Toronto
    'DKK': ['XCSE'],  # Copenhagen
}

test_cases = [
    {"name": "AMADEUS IT", "isin": "ES0109067019", "currency": "EUR"},
    {"name": "ACCENTURE PLC", "isin": "IE00B4BNMY34", "currency": "USD"},
    {"name": "AIRTEL AFRI. WI", "isin": "GB00BKDRYJ47", "currency": "GBP"},
    {"name": "CONSUN PHARMACEUTICAL", "isin": "KYG2524A1031", "currency": "HKD"},
    {"name": "AUTO PARTNER SA", "isin": "PLATPRT00018", "currency": "PLN"},
    {"name": "PAX GLOBAL", "isin": "BMG6955J1036", "currency": "HKD"},
]

print("\n" + "="*80)
print("ANÁLISIS DE RESULTADOS OPENFIGI")
print("="*80)

for test in test_cases:
    print(f"\n{'='*80}")
    print(f"ASSET: {test['name']}")
    print(f"{'='*80}")
    print(f"ISIN: {test['isin']}")
    print(f"Moneda DeGiro: {test['currency']}")
    
    payload = [{"idType": "ID_ISIN", "idValue": test['isin']}]
    
    try:
        response = requests.post(OPENFIGI_URL, headers={'Content-Type': 'application/json'}, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result and len(result) > 0 and 'data' in result[0]:
                data_items = result[0]['data']
                print(f"\n📊 Total resultados: {len(data_items)}")
                
                # Filtrar por exchanges principales de la moneda
                primary_exchanges = CURRENCY_TO_PRIMARY_EXCHANGE.get(test['currency'], [])
                matching_exchange = [d for d in data_items if d.get('exchCode') in primary_exchanges]
                
                if matching_exchange:
                    print(f"\n✅ Resultado(s) del exchange principal para {test['currency']}:")
                    for item in matching_exchange[:3]:  # Max 3
                        print(f"   Ticker: {item.get('ticker')}")
                        print(f"   Exchange: {item.get('exchCode')} ({item.get('name', 'N/A')})")
                        print(f"   Security Type: {item.get('securityType')}")
                        print()
                else:
                    print(f"\n⚠️  No se encontró resultado para exchanges principales: {', '.join(primary_exchanges)}")
                    print(f"\n   Exchanges disponibles (primeros 10):")
                    seen_exchanges = set()
                    for item in data_items[:10]:
                        ex_code = item.get('exchCode')
                        if ex_code and ex_code not in seen_exchanges:
                            seen_exchanges.add(ex_code)
                            print(f"      {ex_code}: {item.get('ticker')} ({item.get('name', 'N/A')})")
                
                # Mostrar tickers únicos
                unique_tickers = list(set([d.get('ticker') for d in data_items if d.get('ticker')]))
                print(f"\n   Tickers únicos encontrados ({len(unique_tickers)}): {', '.join(unique_tickers[:10])}")
                
            else:
                print(f"\n❌ No se encontraron datos")
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

print("\n" + "="*80)
print("CONCLUSIONES")
print("="*80)
print("""
1. OpenFIGI NO devuelve el campo 'currency'
2. Un ISIN puede tener 50-90 resultados (cross-listings)
3. Necesitamos filtrar por MIC code del exchange principal
4. Los tickers varían según el exchange (327, 327HKD, P8X, etc.)

ESTRATEGIA PROPUESTA:
- Usar un mapeo de Currency → Primary Exchange (MIC)
- Filtrar resultados por ese exchange
- Si no hay match, usar el primer resultado con exchCode más conocido
- Guardar: ticker + exchCode (MIC)
""")
print()

