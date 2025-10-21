"""
Test OpenFIGI con diferentes combinaciones de parámetros
Para encontrar la mejor estrategia
"""
import requests
import json
from time import sleep

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Un caso de prueba
test_case = {
    "name": "ALPHABET INC. - CLASS A",
    "isin": "US02079K3059",
    "currency": "USD",
    "exchCode": "XNAS"
}

print("\n" + "="*80)
print(f"COMPARACIÓN DE ESTRATEGIAS PARA: {test_case['name']}")
print("="*80)
print(f"ISIN: {test_case['isin']}")
print(f"Currency: {test_case['currency']}")
print(f"ExchCode: {test_case['exchCode']}\n")

strategies = [
    {
        "name": "Solo ISIN",
        "payload": {"idType": "ID_ISIN", "idValue": test_case['isin']}
    },
    {
        "name": "ISIN + Currency",
        "payload": {"idType": "ID_ISIN", "idValue": test_case['isin'], "currency": test_case['currency']}
    },
    {
        "name": "ISIN + ExchCode",
        "payload": {"idType": "ID_ISIN", "idValue": test_case['isin'], "exchCode": test_case['exchCode']}
    },
    {
        "name": "ISIN + Currency + ExchCode",
        "payload": {"idType": "ID_ISIN", "idValue": test_case['isin'], "currency": test_case['currency'], "exchCode": test_case['exchCode']}
    }
]

headers = {'Content-Type': 'application/json'}

for i, strategy in enumerate(strategies, 1):
    print("="*80)
    print(f"ESTRATEGIA {i}: {strategy['name']}")
    print("="*80)
    print(f"Payload: {json.dumps(strategy['payload'], indent=2)}\n")
    
    try:
        response = requests.post(OPENFIGI_URL, headers=headers, json=[strategy['payload']], timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result and len(result) > 0 and 'data' in result[0]:
                data_items = result[0]['data']
                print(f"✅ Resultados: {len(data_items)}")
                
                if len(data_items) > 0:
                    print(f"\n📋 Primeros 3 resultados:")
                    for j, item in enumerate(data_items[:3], 1):
                        print(f"   {j}. Ticker: {item.get('ticker')} | Exchange: {item.get('exchCode')} | Type: {item.get('securityType')}")
                    
                    # Buscar el que coincide con XNAS
                    xnas_results = [d for d in data_items if d.get('exchCode') == 'XNAS']
                    if xnas_results:
                        print(f"\n   ✅ Encontrado en XNAS: {len(xnas_results)} resultado(s)")
                        print(f"      Ticker: {xnas_results[0].get('ticker')}")
                    else:
                        print(f"\n   ⚠️  XNAS no encontrado en los {len(data_items)} resultados")
            else:
                print(f"❌ Sin datos")
                if 'error' in result[0]:
                    print(f"Error: {result[0]['error']}")
        else:
            print(f"❌ Error {response.status_code}")
    
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    print()
    sleep(0.5)

print("="*80)
print("CONCLUSIÓN")
print("="*80)
print("""
🎯 MEJOR ESTRATEGIA:
   1. Usar ISIN + Currency (filtra por moneda)
   2. De los resultados, buscar el que coincida con exchCode del CSV
   3. Si no hay coincidencia, usar el primer resultado
   
📝 LÓGICA:
   - OpenFIGI no acepta bien exchCode como filtro inicial
   - Pero SÍ devuelve el exchCode en la respuesta
   - Podemos filtrar manualmente después de recibir los resultados
""")
print()

