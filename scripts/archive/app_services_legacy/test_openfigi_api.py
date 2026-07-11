"""
Script de prueba para OpenFIGI API
Consulta ISINs de ejemplo y muestra los resultados
"""
import requests
import json
from time import sleep

# OpenFIGI API endpoint
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Ejemplos de ISINs de diferentes monedas (de nuestra BD)
test_cases = [
    {
        "name": "AMADEUS IT",
        "isin": "ES0109067019",
        "currency": "EUR",
        "description": "Acción española (Madrid)"
    },
    {
        "name": "ACCENTURE PLC",
        "isin": "IE00B4BNMY34",
        "currency": "USD",
        "description": "ADR listado en NYSE"
    },
    {
        "name": "AIRTEL AFRI. WI",
        "isin": "GB00BKDRYJ47",
        "currency": "GBP",
        "description": "Acción británica (LSE)"
    },
    {
        "name": "CONSUN PHARMACEUTICAL GROUP",
        "isin": "KYG2524A1031",
        "currency": "HKD",
        "description": "Acción de Hong Kong (HKEX)"
    },
    {
        "name": "AUTO PARTNER SA",
        "isin": "PLATPRT00018",
        "currency": "PLN",
        "description": "Acción polaca (WSE)"
    },
    {
        "name": "GEORGIA CAPITAL",
        "isin": "GB00BF4HYV08",
        "currency": "GBX",
        "description": "Acción británica (pence)"
    },
    {
        "name": "PAX GLOBAL TECHNOLOGY LTD",
        "isin": "BMG6955J1036",
        "currency": "HKD",
        "description": "Bermuda registrada, cotiza en HK"
    }
]

print("\n" + "="*80)
print("TESTING OPENFIGI API CON ISINS DE DEGIRO")
print("="*80)
print(f"\nAPI Endpoint: {OPENFIGI_URL}")
print("Método: POST con JSON body")
print("\n" + "="*80)

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"TEST {i}/{len(test_cases)}: {test['name']}")
    print(f"{'='*80}")
    print(f"ISIN: {test['isin']}")
    print(f"Moneda esperada: {test['currency']}")
    print(f"Descripción: {test['description']}")
    print()
    
    # Preparar request
    payload = [
        {
            "idType": "ID_ISIN",
            "idValue": test['isin']
        }
    ]
    
    try:
        # Hacer request a OpenFIGI
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            OPENFIGI_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result and len(result) > 0 and 'data' in result[0]:
                data_items = result[0]['data']
                print(f"✅ Resultados encontrados: {len(data_items)}")
                print()
                
                # Mostrar todos los resultados (pueden haber múltiples exchanges)
                for j, item in enumerate(data_items, 1):
                    print(f"   Resultado {j}:")
                    print(f"      Ticker: {item.get('ticker', 'N/A')}")
                    print(f"      Exchange (MIC): {item.get('exchCode', 'N/A')}")
                    print(f"      Exchange Name: {item.get('marketSector', 'N/A')}")
                    print(f"      Security Type: {item.get('securityType', 'N/A')}")
                    print(f"      Security Type 2: {item.get('securityType2', 'N/A')}")
                    print(f"      Name: {item.get('name', 'N/A')}")
                    print(f"      Currency: {item.get('currency', 'N/A')}")
                    print(f"      Market Sector: {item.get('marketSector', 'N/A')}")
                    print()
                    
                # Verificar si alguno coincide con nuestra moneda
                matching = [d for d in data_items if d.get('currency') == test['currency']]
                if matching:
                    print(f"   ✅ {len(matching)} resultado(s) coinciden con moneda {test['currency']}")
                else:
                    print(f"   ⚠️  Ningún resultado coincide con moneda {test['currency']}")
                    currencies_found = [d.get('currency') for d in data_items]
                    print(f"   Monedas encontradas: {', '.join(currencies_found)}")
            else:
                print(f"   ❌ No se encontraron datos para este ISIN")
                if 'error' in result[0]:
                    print(f"   Error: {result[0]['error']}")
        
        elif response.status_code == 429:
            print(f"⚠️  Rate limit alcanzado (429). Esperando...")
            sleep(60)
        
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:200]}")
    
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    # Pequeña pausa entre requests para no saturar la API
    if i < len(test_cases):
        sleep(0.5)

print("\n" + "="*80)
print("TESTING COMPLETADO")
print("="*80)
print("\n💡 Análisis:")
print("   - ¿OpenFIGI devuelve tickers para todos los ISINs?")
print("   - ¿Hay múltiples resultados por ISIN?")
print("   - ¿Coincide la moneda devuelta con la esperada?")
print("   - ¿Qué exchange (MIC code) se devuelve?")
print()

