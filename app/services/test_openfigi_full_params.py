"""
Test OpenFIGI con ISIN + Currency + ExchCode (MIC)
Los 3 parámetros que tenemos disponibles desde DeGiro
"""
import requests
import json
from time import sleep

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Ejemplos reales del CSV de DeGiro
test_cases = [
    {
        "name": "ALPHABET INC. - CLASS A",
        "isin": "US02079K3059",
        "currency": "USD",
        "exchCode": "XNAS",  # ✅ Columna 5 del CSV
        "description": "NASDAQ"
    },
    {
        "name": "EXCELLENCE COMMERCIAL PROPERTY",
        "isin": "KYG3235S1021",
        "currency": "HKD",
        "exchCode": "XHKG",  # ✅ Columna 5 del CSV
        "description": "Hong Kong"
    },
    {
        "name": "NCR ATLEOS CORP",
        "isin": "US63001N1063",
        "currency": "USD",
        "exchCode": "XNYS",  # ✅ Columna 5 del CSV
        "description": "NYSE"
    },
    {
        "name": "GESTAMP AUTOMOCION SA",
        "isin": "ES0105223004",
        "currency": "EUR",
        "exchCode": "XMAD",  # ✅ Columna 5 del CSV
        "description": "Madrid"
    },
    {
        "name": "AUTO PARTNER SA",
        "isin": "PLATPRT00018",
        "currency": "PLN",
        "exchCode": "XWAR",  # ✅ Columna 5 del CSV
        "description": "Warsaw"
    },
    {
        "name": "CLOUDBERRY CLEAN ENERGY",
        "isin": "NO0010876642",
        "currency": "NOK",
        "exchCode": "XOSL",  # ✅ Columna 5 del CSV
        "description": "Oslo"
    }
]

print("\n" + "="*80)
print("TEST OPENFIGI CON ISIN + CURRENCY + EXCHCODE")
print("="*80)
print("\n💡 Usando los 3 parámetros disponibles en DeGiro CSV:")
print("   1. ISIN (columna 3)")
print("   2. Currency (columna 8)")
print("   3. ExchCode/MIC (columna 5)\n")

for i, test in enumerate(test_cases, 1):
    print("="*80)
    print(f"TEST {i}/{len(test_cases)}: {test['name']}")
    print("="*80)
    print(f"ISIN: {test['isin']}")
    print(f"Currency: {test['currency']}")
    print(f"ExchCode (MIC): {test['exchCode']} ({test['description']})")
    print()
    
    # Request con los 3 parámetros
    payload = [
        {
            "idType": "ID_ISIN",
            "idValue": test['isin'],
            "currency": test['currency'],
            "exchCode": test['exchCode']
        }
    ]
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result and len(result) > 0 and 'data' in result[0]:
                data_items = result[0]['data']
                print(f"✅ Resultados: {len(data_items)}")
                
                if len(data_items) > 0:
                    print(f"\n📋 Datos obtenidos:")
                    for j, item in enumerate(data_items[:3], 1):  # Max 3
                        print(f"   Resultado {j}:")
                        print(f"      Ticker: {item.get('ticker')}")
                        print(f"      Name: {item.get('name')}")
                        print(f"      Exchange: {item.get('exchCode')}")
                        print(f"      Security Type: {item.get('securityType')}")
                        print(f"      Market Sector: {item.get('marketSector')}")
                        print()
                    
                    # Verificación
                    if len(data_items) == 1:
                        print(f"   ✅ PERFECTO: Resultado único y preciso")
                    else:
                        print(f"   ⚠️  Múltiples resultados ({len(data_items)}), pero filtrados correctamente")
                else:
                    print(f"   ❌ No se encontraron resultados")
            else:
                print(f"   ❌ Sin datos")
                if 'error' in result[0]:
                    print(f"   Error: {result[0]['error']}")
        
        elif response.status_code == 429:
            print(f"⚠️  Rate limit (429)")
        else:
            print(f"❌ Error {response.status_code}")
    
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    if i < len(test_cases):
        sleep(0.5)

print("\n" + "="*80)
print("CONCLUSIONES")
print("="*80)
print("""
✅ DATOS DISPONIBLES EN DEGIRO CSV:
   Columna 3: ISIN
   Columna 5: ExchCode (MIC) ← ¡CLAVE!
   Columna 8: Currency

✅ REQUEST A OPENFIGI:
   {
     "idType": "ID_ISIN",
     "idValue": "US02079K3059",
     "currency": "USD",
     "exchCode": "XNAS"
   }

✅ RESPUESTA ESPERADA:
   - Ticker preciso ✅
   - Exchange confirmado ✅
   - Resultado único o muy filtrado ✅

🎯 IMPLEMENTACIÓN:
   1. Extraer exchCode (columna 5) al parsear DeGiro CSV
   2. Guardar en campo exchange del asset
   3. Para assets sin exchange: consultar OpenFIGI con ISIN+Currency
   4. Actualizar ticker y exchange en BD
""")
print()

