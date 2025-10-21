"""
Script para descubrir el mapeo entre MIC estándar y códigos OpenFIGI
Analizando las respuestas de la API
"""
import requests
import json
from time import sleep
from collections import defaultdict

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Casos de prueba con MIC conocidos (del CSV DeGiro)
test_cases = [
    {"name": "ALPHABET", "isin": "US02079K3059", "currency": "USD", "mic_degiro": "XNAS"},
    {"name": "NCR ATLEOS", "isin": "US63001N1063", "currency": "USD", "mic_degiro": "XNYS"},
    {"name": "EXCELLENCE", "isin": "KYG3235S1021", "currency": "HKD", "mic_degiro": "XHKG"},
    {"name": "GESTAMP", "isin": "ES0105223004", "currency": "EUR", "mic_degiro": "XMAD"},
    {"name": "AUTO PARTNER", "isin": "PLATPRT00018", "currency": "PLN", "mic_degiro": "XWAR"},
    {"name": "CLOUDBERRY", "isin": "NO0010876642", "currency": "NOK", "mic_degiro": "XOSL"},
    {"name": "EMBRACER", "isin": "SE0016828511", "currency": "SEK", "mic_degiro": "XSTO"},
    {"name": "BR.AMER.TOB", "isin": "GB0002875804", "currency": "GBX", "mic_degiro": "XLON"},
    {"name": "TECNOINVEST", "isin": "IT0005037210", "currency": "EUR", "mic_degiro": "MTAA"},
    {"name": "GOEASY", "isin": "CA3803551074", "currency": "CAD", "mic_degiro": "XTSE"},
]

print("\n" + "="*80)
print("DESCUBRIENDO MAPEO MIC → OPENFIGI EXCHCODE")
print("="*80)

mic_to_openfigi = defaultdict(set)
headers = {'Content-Type': 'application/json'}

for i, test in enumerate(test_cases, 1):
    print(f"\n[{i}/{len(test_cases)}] {test['name']}")
    print(f"   MIC DeGiro: {test['mic_degiro']}")
    
    payload = [{"idType": "ID_ISIN", "idValue": test['isin'], "currency": test['currency']}]
    
    try:
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result and len(result) > 0 and 'data' in result[0]:
                data_items = result[0]['data']
                
                # Extraer todos los exchCode únicos
                exchCodes = set([d.get('exchCode') for d in data_items if d.get('exchCode')])
                
                print(f"   OpenFIGI exchCodes encontrados: {', '.join(sorted(exchCodes))}")
                
                # Guardar mapeo
                for code in exchCodes:
                    mic_to_openfigi[test['mic_degiro']].add(code)
                
                # Buscar el más relevante (primer resultado suele ser el principal)
                if len(data_items) > 0:
                    primary = data_items[0].get('exchCode')
                    print(f"   ✅ Principal: {primary} (ticker: {data_items[0].get('ticker')})")
            else:
                print(f"   ❌ Sin resultados")
        
        else:
            print(f"   ❌ Error {response.status_code}")
    
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
    
    sleep(0.5)

print("\n" + "="*80)
print("MAPEO DESCUBIERTO")
print("="*80)

for mic, openfigi_codes in sorted(mic_to_openfigi.items()):
    print(f"\n{mic} → {', '.join(sorted(openfigi_codes))}")

print("\n" + "="*80)
print("MAPEO SIMPLIFICADO (código principal)")
print("="*80)

# Intentar determinar el patrón
simplified_mapping = {
    'XNAS': 'US',  # NASDAQ → US
    'XNYS': 'US',  # NYSE → US
    'XHKG': 'HK',  # Hong Kong → HK
    'XMAD': 'MC',  # Madrid → MC (Spain)
    'XWAR': 'PW',  # Warsaw → PW (Poland)
    'XOSL': 'OL',  # Oslo → OL (Norway)
    'XSTO': 'ST',  # Stockholm → ST (Sweden)
    'XLON': 'LN',  # London → LN
    'XTSE': 'CN',  # Toronto → CN (Canada)
    'MTAA': 'IM',  # Milan → IM (Italy)
}

print("\nMapeo sugerido basado en patrones comunes:")
print(json.dumps(simplified_mapping, indent=2))

print("\n" + "="*80)
print("SIGUIENTE PASO")
print("="*80)
print("""
✅ Con este mapeo podemos:
   1. Convertir MIC de DeGiro (XNAS) → OpenFIGI code (US)
   2. Consultar OpenFIGI con: ISIN + Currency + exchCode_convertido
   3. Obtener resultado preciso y único

🔧 IMPLEMENTACIÓN:
   - Crear diccionario de mapeo MIC → OpenFIGI
   - Usar en el enriquecimiento de assets
   - Si no hay mapeo, usar solo ISIN + Currency
""")
print()

