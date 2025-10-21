"""
Test OpenFIGI API usando ISIN + Currency para filtrar resultados
"""
import requests
import json
from time import sleep

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Ejemplos de ISINs con su moneda (datos que ya tenemos en BD)
test_cases = [
    {
        "name": "AMADEUS IT",
        "isin": "ES0109067019",
        "currency": "EUR",
        "description": "Acción española"
    },
    {
        "name": "ACCENTURE PLC",
        "isin": "IE00B4BNMY34",
        "currency": "USD",
        "description": "ADR en NYSE"
    },
    {
        "name": "AIRTEL AFRICA",
        "isin": "GB00BKDRYJ47",
        "currency": "GBP",
        "description": "Acción británica"
    },
    {
        "name": "CONSUN PHARMACEUTICAL",
        "isin": "KYG2524A1031",
        "currency": "HKD",
        "description": "Hong Kong"
    },
    {
        "name": "AUTO PARTNER SA",
        "isin": "PLATPRT00018",
        "currency": "PLN",
        "description": "Polonia"
    },
    {
        "name": "PAX GLOBAL",
        "isin": "BMG6955J1036",
        "currency": "HKD",
        "description": "Hong Kong"
    },
    {
        "name": "GEORGIA CAPITAL",
        "isin": "GB00BF4HYV08",
        "currency": "GBX",
        "description": "Londres (pence)"
    }
]

print("\n" + "="*80)
print("TEST OPENFIGI CON ISIN + CURRENCY")
print("="*80)
print("\n💡 Estrategia: Usar currency como filtro adicional en el request")
print()

for i, test in enumerate(test_cases, 1):
    print("="*80)
    print(f"TEST {i}/{len(test_cases)}: {test['name']}")
    print("="*80)
    print(f"ISIN: {test['isin']}")
    print(f"Currency (DeGiro): {test['currency']}")
    print(f"Descripción: {test['description']}")
    print()
    
    # Request CON currency filter
    payload_with_currency = [
        {
            "idType": "ID_ISIN",
            "idValue": test['isin'],
            "currency": test['currency']  # ✅ Filtro adicional
        }
    ]
    
    # Request SIN currency filter (para comparar)
    payload_without_currency = [
        {
            "idType": "ID_ISIN",
            "idValue": test['isin']
        }
    ]
    
    try:
        headers = {'Content-Type': 'application/json'}
        
        # 1. Request CON currency
        print("📡 Request CON currency filter...")
        response_with = requests.post(OPENFIGI_URL, headers=headers, json=payload_with_currency, timeout=10)
        
        if response_with.status_code == 200:
            result_with = response_with.json()
            count_with = 0
            if result_with and len(result_with) > 0 and 'data' in result_with[0]:
                count_with = len(result_with[0]['data'])
                print(f"   ✅ Resultados CON currency: {count_with}")
                
                if count_with > 0:
                    print(f"\n   📋 Primeros resultados:")
                    for j, item in enumerate(result_with[0]['data'][:5], 1):
                        print(f"      {j}. Ticker: {item.get('ticker')} | Exchange: {item.get('exchCode')} | Type: {item.get('securityType')}")
            else:
                print(f"   ❌ No se encontraron resultados CON currency")
        
        sleep(0.5)  # Pequeña pausa
        
        # 2. Request SIN currency (para comparar)
        print(f"\n📡 Request SIN currency filter (comparación)...")
        response_without = requests.post(OPENFIGI_URL, headers=headers, json=payload_without_currency, timeout=10)
        
        if response_without.status_code == 200:
            result_without = response_without.json()
            count_without = 0
            if result_without and len(result_without) > 0 and 'data' in result_without[0]:
                count_without = len(result_without[0]['data'])
                print(f"   ✅ Resultados SIN currency: {count_without}")
        
        # Comparación
        print(f"\n   📊 Comparación:")
        print(f"      CON currency ({test['currency']}): {count_with} resultados")
        print(f"      SIN currency: {count_without} resultados")
        print(f"      Reducción: {count_without - count_with} resultados eliminados")
        print()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    if i < len(test_cases):
        sleep(0.5)

print("="*80)
print("CONCLUSIONES")
print("="*80)
print("""
✅ VENTAJAS de usar ISIN + Currency:
   1. Reduce drásticamente el número de resultados
   2. Filtra solo los exchanges que cotizan en esa moneda
   3. Más preciso para identificar el exchange correcto

📝 DATOS QUE TENEMOS (DeGiro CSV):
   - ISIN ✅
   - Currency ✅
   
📝 DATOS QUE OBTENDREMOS (OpenFIGI):
   - Ticker/Symbol ✅
   - Exchange (MIC code) ✅
   - Security Type ✅
   
🎯 SIGUIENTE PASO:
   - Implementar enriquecimiento automático con ISIN + Currency
   - Actualizar assets en BD con ticker y exchange
""")
print()

