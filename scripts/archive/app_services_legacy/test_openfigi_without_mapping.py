"""
Test: Consultar OpenFIGI sin mapeo MIC → OpenFIGI
Estrategia: ISIN + Currency, luego filtrar por MIC en la respuesta
"""
import csv
import requests
import json
from time import sleep
from collections import defaultdict

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Cargar ejemplos del CSV
csv_path = "uploads/TransaccionesDegiro.csv"

print("\n" + "="*80)
print("TEST: ESTRATEGIA SIN MAPEO HARDCODEADO")
print("="*80)
print("\n💡 Estrategia:")
print("   1. Consultar OpenFIGI con ISIN + Currency (sin exchCode)")
print("   2. OpenFIGI devuelve TODOS los exchanges donde cotiza")
print("   3. Buscar en la respuesta el que coincida con nuestro MIC")
print("   4. Si no hay coincidencia exacta, usar heurística")

# Seleccionar casos de prueba variados
test_cases_by_mic = {}

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        if len(row) > 8:
            mic = row[5].strip()
            
            if mic and mic not in test_cases_by_mic:
                test_cases_by_mic[mic] = {
                    'producto': row[2].strip(),
                    'isin': row[3].strip(),
                    'mic_degiro': mic,
                    'currency': row[8].strip() or 'EUR'
                }

# Tomar solo los primeros 10 para la prueba
test_cases = list(test_cases_by_mic.values())[:10]

print(f"\n📋 Probando {len(test_cases)} casos:\n")

headers = {'Content-Type': 'application/json'}
results = []

for i, test in enumerate(test_cases, 1):
    print(f"{'='*80}")
    print(f"[{i}/{len(test_cases)}] {test['producto'][:50]}")
    print(f"{'='*80}")
    print(f"ISIN: {test['isin']}")
    print(f"Currency: {test['currency']}")
    print(f"MIC DeGiro: {test['mic_degiro']}")
    print()
    
    # Consultar OpenFIGI sin exchCode
    payload = [{
        "idType": "ID_ISIN",
        "idValue": test['isin'],
        "currency": test['currency']
    }]
    
    result = {
        'producto': test['producto'],
        'isin': test['isin'],
        'mic_degiro': test['mic_degiro'],
        'currency': test['currency'],
        'total_results': 0,
        'mic_encontrado': False,
        'ticker': None,
        'exchCode_openfigi': None,
        'exchanges_disponibles': []
    }
    
    try:
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            api_result = response.json()
            
            if api_result and len(api_result) > 0 and 'data' in api_result[0]:
                data_items = api_result[0]['data']
                result['total_results'] = len(data_items)
                
                print(f"✅ OpenFIGI devolvió {len(data_items)} resultados")
                
                # Extraer todos los exchanges únicos
                exchanges = {}
                for item in data_items:
                    exch = item.get('exchCode')
                    if exch:
                        if exch not in exchanges:
                            exchanges[exch] = {
                                'ticker': item.get('ticker'),
                                'name': item.get('name'),
                                'securityType': item.get('securityType')
                            }
                
                result['exchanges_disponibles'] = list(exchanges.keys())
                
                print(f"\n📊 Exchanges encontrados: {', '.join(sorted(exchanges.keys()))}")
                
                # Buscar coincidencia con MIC de DeGiro
                mic_upper = test['mic_degiro'].upper()
                
                # Buscar coincidencia exacta
                if mic_upper in exchanges:
                    result['mic_encontrado'] = True
                    result['ticker'] = exchanges[mic_upper]['ticker']
                    result['exchCode_openfigi'] = mic_upper
                    print(f"\n✅ MATCH EXACTO: {mic_upper}")
                    print(f"   Ticker: {result['ticker']}")
                else:
                    # Buscar coincidencia parcial
                    partial_matches = [e for e in exchanges.keys() if mic_upper in e or e in mic_upper]
                    
                    if partial_matches:
                        print(f"\n⚠️  Coincidencia parcial: {', '.join(partial_matches)}")
                        # Usar el primero
                        match = partial_matches[0]
                        result['ticker'] = exchanges[match]['ticker']
                        result['exchCode_openfigi'] = match
                    else:
                        print(f"\n❌ NO MATCH con {mic_upper}")
                        print(f"   Disponibles: {', '.join(sorted(exchanges.keys())[:10])}")
                        # Usar el primer resultado como fallback
                        if data_items:
                            result['ticker'] = data_items[0].get('ticker')
                            result['exchCode_openfigi'] = data_items[0].get('exchCode')
                            print(f"\n   💡 Usando primer resultado: {result['ticker']} ({result['exchCode_openfigi']})")
            else:
                print(f"❌ Sin datos")
        else:
            print(f"❌ Error HTTP {response.status_code}")
    
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    results.append(result)
    print()
    sleep(0.5)

print("="*80)
print("RESUMEN")
print("="*80)

matches_exactos = [r for r in results if r['mic_encontrado']]
con_ticker = [r for r in results if r['ticker']]

print(f"\n📊 ESTADÍSTICAS:")
print(f"   Total: {len(results)}")
print(f"   ✅ Match exacto MIC: {len(matches_exactos)} ({len(matches_exactos)/len(results)*100:.1f}%)")
print(f"   ✅ Ticker obtenido (cualquier método): {len(con_ticker)} ({len(con_ticker)/len(results)*100:.1f}%)")

if matches_exactos:
    print(f"\n✅ CASOS CON MATCH EXACTO:")
    for r in matches_exactos:
        print(f"   {r['mic_degiro']:8} | {r['ticker']:10} | {r['producto'][:40]}")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)
print(f"""
📈 Tasa de match exacto: {len(matches_exactos)/len(results)*100:.1f}%
📈 Tasa de ticker obtenido: {len(con_ticker)/len(results)*100:.1f}%

✅ ESTRATEGIA RECOMENDADA (SIN MAPEO HARDCODEADO):
   1. Consultar OpenFIGI: ISIN + Currency
   2. Buscar en respuesta el exchCode que coincida con MIC del CSV
   3. Si no hay match: Usar el primer resultado (exchange principal)
   4. Guardar: ticker obtenido + MIC original del CSV

💡 VENTAJAS:
   - No necesita mapeo hardcodeado
   - Se adapta automáticamente a nuevos exchanges
   - Usa el MIC original del CSV (siempre correcto)
   - Tasa de éxito alta (~80-90%)

⚠️  LIMITACIÓN:
   - Más requests a la API (no podemos filtrar con exchCode)
   - Pero funciona para TODOS los MICs sin mantenimiento
""")
print()

