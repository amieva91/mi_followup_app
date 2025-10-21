"""
Test exhaustivo de todos los códigos MIC del CSV TransaccionesDegiro
Para calcular la tasa de éxito/error
"""
import csv
import requests
import json
from time import sleep
from collections import defaultdict

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Mapeo MIC → OpenFIGI (extendido con más exchanges comunes)
MIC_TO_OPENFIGI = {
    # US Markets
    'XNAS': 'US',   # NASDAQ
    'XNYS': 'US',   # NYSE
    'ARCX': 'US',   # NYSE Arca
    'BATS': 'US',   # BATS
    'EDGA': 'US',   # EDGA
    'EDGX': 'US',   # EDGX
    'IEXG': 'US',   # IEX
    'MEMX': 'US',   # MEMX
    
    # Europe
    'XLON': 'LN',   # London
    'XMAD': 'SM',   # Madrid
    'XPAR': 'FP',   # Paris
    'XETR': 'GY',   # Xetra (Germany)
    'XFRA': 'GY',   # Frankfurt
    'XMIL': 'IM',   # Milan
    'MTAA': 'IM',   # Milan (MTA)
    'XAMS': 'NA',   # Amsterdam
    'XLIS': 'PL',   # Lisbon
    'XBRU': 'BB',   # Brussels
    'XSWX': 'SW',   # Swiss
    'XWAR': 'PW',   # Warsaw
    'XPRA': 'CP',   # Prague
    'XBUD': 'BH',   # Budapest
    'XATH': 'GA',   # Athens
    'XOSL': 'NO',   # Oslo
    'XSTO': 'ST',   # Stockholm
    'XCSE': 'DC',   # Copenhagen
    'XHEL': 'HE',   # Helsinki
    'XICE': 'IR',   # Iceland
    
    # Asia
    'XHKG': 'HK',   # Hong Kong
    'XSHG': 'CH',   # Shanghai
    'XSHE': 'CH',   # Shenzhen
    'XTKS': 'JP',   # Tokyo
    'XKRX': 'KS',   # Korea
    'XSES': 'SP',   # Singapore
    'XBOM': 'IB',   # Bombay
    'XNSE': 'IN',   # NSE India
    
    # Americas
    'XTSE': 'CN',   # Toronto
    'XTSX': 'CN',   # TSX Venture
    'BVMF': 'BZ',   # Brazil
    'XMEX': 'MM',   # Mexico
    
    # Oceania
    'XASX': 'AU',   # Australia
    'XNZE': 'NZ',   # New Zealand
}

csv_path = "uploads/TransaccionesDegiro.csv"

print("\n" + "="*80)
print("ANÁLISIS EXHAUSTIVO DE CÓDIGOS MIC EN TRANSACCIONES DEGIRO")
print("="*80)

# Paso 1: Extraer todos los MIC únicos con ejemplos
mic_examples = {}

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        if len(row) > 8:
            mic = row[5].strip()  # Columna 5: Centro de negociación
            
            if mic and mic not in mic_examples:
                mic_examples[mic] = {
                    'producto': row[2].strip(),
                    'isin': row[3].strip(),
                    'currency': row[8].strip() if row[8].strip() else 'EUR'
                }

print(f"\n📊 Códigos MIC únicos encontrados: {len(mic_examples)}")
print(f"\n📋 Lista de MICs a probar:")
for mic in sorted(mic_examples.keys()):
    ex = mic_examples[mic]
    mapped = MIC_TO_OPENFIGI.get(mic, '❓')
    print(f"   {mic:8} → {mapped:4} | {ex['producto'][:40]:40} | {ex['currency']}")

print("\n" + "="*80)
print("PROBANDO CON OPENFIGI (ISIN + Currency + ExchCode)")
print("="*80)

headers = {'Content-Type': 'application/json'}
results = []

for i, (mic, data) in enumerate(sorted(mic_examples.items()), 1):
    openfigi_code = MIC_TO_OPENFIGI.get(mic)
    
    result = {
        'mic': mic,
        'openfigi_code': openfigi_code,
        'producto': data['producto'],
        'isin': data['isin'],
        'currency': data['currency'],
        'success': False,
        'result_count': 0,
        'ticker': None,
        'error': None
    }
    
    print(f"\n[{i}/{len(mic_examples)}] {mic} → {openfigi_code or '❌ SIN MAPEO'}")
    print(f"   {data['producto'][:50]}")
    print(f"   ISIN: {data['isin']} | Currency: {data['currency']}")
    
    if not openfigi_code:
        result['error'] = 'Sin mapeo'
        results.append(result)
        print(f"   ⚠️  Sin mapeo en diccionario")
        continue
    
    try:
        payload = [{
            "idType": "ID_ISIN",
            "idValue": data['isin'],
            "currency": data['currency'],
            "exchCode": openfigi_code
        }]
        
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            api_result = response.json()
            
            if api_result and len(api_result) > 0 and 'data' in api_result[0]:
                data_items = api_result[0]['data']
                result['result_count'] = len(data_items)
                
                if len(data_items) > 0:
                    result['success'] = True
                    result['ticker'] = data_items[0].get('ticker')
                    print(f"   ✅ SUCCESS: {len(data_items)} resultado(s) | Ticker: {result['ticker']}")
                else:
                    result['error'] = 'Sin resultados'
                    print(f"   ❌ Sin resultados")
            else:
                result['error'] = 'Sin datos en respuesta'
                print(f"   ❌ Sin datos")
                if 'error' in api_result[0]:
                    result['error'] = api_result[0]['error']
                    print(f"      Error: {result['error']}")
        
        elif response.status_code == 429:
            result['error'] = 'Rate limit'
            print(f"   ⚠️  Rate limit alcanzado")
            sleep(60)
        
        else:
            result['error'] = f'HTTP {response.status_code}'
            print(f"   ❌ Error HTTP {response.status_code}")
    
    except Exception as e:
        result['error'] = str(e)
        print(f"   ❌ Exception: {str(e)}")
    
    results.append(result)
    sleep(0.5)  # Pausa entre requests

print("\n" + "="*80)
print("RESUMEN DE RESULTADOS")
print("="*80)

successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]
no_mapping = [r for r in results if r['error'] == 'Sin mapeo']

print(f"\n📊 ESTADÍSTICAS:")
print(f"   Total MICs probados: {len(results)}")
print(f"   ✅ Éxitos: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
print(f"   ❌ Fallos: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
print(f"   ⚠️  Sin mapeo: {len(no_mapping)} ({len(no_mapping)/len(results)*100:.1f}%)")

if successful:
    print(f"\n✅ MICs QUE FUNCIONAN:")
    for r in successful:
        print(f"   {r['mic']:8} → {r['openfigi_code']:4} | Ticker: {r['ticker']:8} | {r['producto'][:40]}")

if failed:
    print(f"\n❌ MICs QUE FALLAN:")
    for r in failed:
        print(f"   {r['mic']:8} → {r['openfigi_code'] or 'N/A':4} | Error: {r['error']:20} | {r['producto'][:30]}")

print("\n" + "="*80)
print("RECOMENDACIONES")
print("="*80)
print(f"""
📈 Tasa de éxito: {len(successful)/len(results)*100:.1f}%

{'✅ EXCELENTE' if len(successful)/len(results) > 0.8 else '⚠️ MEJORABLE' if len(successful)/len(results) > 0.5 else '❌ NECESITA TRABAJO'}

💡 ACCIONES:
   1. Para MICs exitosos: Usar directamente la estrategia
   2. Para MICs sin mapeo: Ampliar diccionario MIC_TO_OPENFIGI
   3. Para MICs que fallan: Usar fallback (ISIN + Currency sin exchCode)
""")
print()

