"""
Test OpenFIGI usando el mapeo correcto MIC → OpenFIGI
"""
import requests
import json
from time import sleep

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Mapeo descubierto (MIC → OpenFIGI código principal)
MIC_TO_OPENFIGI = {
    'XNAS': 'US',
    'XNYS': 'US',
    'XHKG': 'HK',
    'XMAD': 'SM',
    'XWAR': 'PW',
    'XOSL': 'NO',
    'XSTO': 'ST',
    'XLON': 'LN',
    'XTSE': 'CN',
    'XPAR': 'FP',
    'XETR': 'GY',
    'MTAA': 'IM',
}

test_cases = [
    {"name": "ALPHABET", "isin": "US02079K3059", "currency": "USD", "mic": "XNAS"},
    {"name": "EXCELLENCE", "isin": "KYG3235S1021", "currency": "HKD", "mic": "XHKG"},
    {"name": "GESTAMP", "isin": "ES0105223004", "currency": "EUR", "mic": "XMAD"},
    {"name": "AUTO PARTNER", "isin": "PLATPRT00018", "currency": "PLN", "mic": "XWAR"},
]

print("\n" + "="*80)
print("TEST CON MAPEO CORRECTO MIC → OPENFIGI")
print("="*80)

headers = {'Content-Type': 'application/json'}

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"TEST {i}/{len(test_cases)}: {test['name']}")
    print(f"{'='*80}")
    print(f"ISIN: {test['isin']}")
    print(f"Currency: {test['currency']}")
    print(f"MIC DeGiro: {test['mic']}")
    
    openfigi_code = MIC_TO_OPENFIGI.get(test['mic'])
    print(f"OpenFIGI Code: {openfigi_code}")
    print()
    
    if not openfigi_code:
        print("   ⚠️  Sin mapeo, saltando...")
        continue
    
    # Probar 2 estrategias
    strategies = [
        {
            "name": "ISIN + Currency",
            "payload": {"idType": "ID_ISIN", "idValue": test['isin'], "currency": test['currency']}
        },
        {
            "name": "ISIN + Currency + ExchCode",
            "payload": {"idType": "ID_ISIN", "idValue": test['isin'], "currency": test['currency'], "exchCode": openfigi_code}
        }
    ]
    
    for strategy in strategies:
        print(f"   📡 {strategy['name']}:")
        
        try:
            response = requests.post(OPENFIGI_URL, headers=headers, json=[strategy['payload']], timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if result and len(result) > 0 and 'data' in result[0]:
                    data_items = result[0]['data']
                    print(f"      ✅ Resultados: {len(data_items)}")
                    
                    if len(data_items) > 0:
                        first = data_items[0]
                        print(f"      Ticker: {first.get('ticker')} | Exchange: {first.get('exchCode')} | Type: {first.get('securityType')}")
                else:
                    print(f"      ❌ Sin datos")
                    if 'error' in result[0]:
                        print(f"      Error: {result[0]['error']}")
            else:
                print(f"      ❌ Error {response.status_code}")
        
        except Exception as e:
            print(f"      ❌ Exception: {str(e)}")
        
        sleep(0.3)
    
    print()

print("="*80)
print("CONCLUSIONES")
print("="*80)
print("""
📊 RESULTADOS:
   - ISIN + Currency: Funciona pero devuelve muchos resultados
   - ISIN + Currency + ExchCode (convertido): Depende del exchange
   
✅ ESTRATEGIA ÓPTIMA:
   1. Usar MIC de DeGiro directamente como 'exchange' en BD
   2. Para obtener ticker: consultar OpenFIGI con ISIN + Currency
   3. Filtrar manualmente buscando el exchCode que coincida
   4. Si no hay coincidencia exacta, usar el primer resultado
   
💡 VENTAJA:
   - No dependemos de que el filtro exchCode funcione en OpenFIGI
   - Tenemos el exchange correcto del CSV
   - Solo necesitamos el ticker de OpenFIGI
""")
print()

