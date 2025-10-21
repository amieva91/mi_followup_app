"""
Simulación SIMPLE: ISIN + Currency → Primer resultado
Un ejemplo por cada MIC diferente en DeGiro
"""
import csv
import requests
import json
from time import sleep

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

csv_path = "uploads/TransaccionesDegiro.csv"

print("\n" + "="*80)
print("SIMULACIÓN: ESTRATEGIA SIMPLE (ISIN + CURRENCY)")
print("="*80)
print("\n💡 Estrategia:")
print("   1. Consultar OpenFIGI con: ISIN + Currency")
print("   2. Tomar el PRIMER resultado")
print("   3. Guardar: ticker + MIC original del CSV")
print()

# Recopilar un ejemplo por cada MIC único
mic_examples = {}

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        if len(row) > 8:
            mic = row[5].strip()
            
            if mic and mic not in mic_examples:
                mic_examples[mic] = {
                    'producto': row[2].strip(),
                    'isin': row[3].strip(),
                    'mic_degiro': mic,
                    'currency': row[8].strip() or 'EUR',
                    'bolsa_de': row[4].strip() if len(row) > 4 else ''
                }

test_cases = list(mic_examples.values())

print(f"📊 Total MICs únicos en CSV: {len(test_cases)}")
print(f"📋 Probando todos ({len(test_cases)} casos)...\n")

headers = {'Content-Type': 'application/json'}
results = []

for i, test in enumerate(test_cases, 1):
    print(f"[{i:2d}/{len(test_cases)}] {test['mic_degiro']:8} | {test['producto'][:40]:40} ", end='')
    
    result = {
        'mic_degiro': test['mic_degiro'],
        'bolsa_de': test['bolsa_de'],
        'producto': test['producto'],
        'isin': test['isin'],
        'currency': test['currency'],
        'success': False,
        'ticker': None,
        'exchange_openfigi': None,
        'name_openfigi': None,
        'total_results': 0,
        'error': None
    }
    
    try:
        payload = [{
            "idType": "ID_ISIN",
            "idValue": test['isin'],
            "currency": test['currency']
        }]
        
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            api_result = response.json()
            
            if api_result and len(api_result) > 0 and 'data' in api_result[0]:
                data_items = api_result[0]['data']
                result['total_results'] = len(data_items)
                
                if len(data_items) > 0:
                    first = data_items[0]
                    result['success'] = True
                    result['ticker'] = first.get('ticker')
                    result['exchange_openfigi'] = first.get('exchCode')
                    result['name_openfigi'] = first.get('name')
                    
                    print(f"| ✅ {result['ticker']:10} ({result['exchange_openfigi']}) [{result['total_results']:2d} res]")
                else:
                    result['error'] = 'Sin resultados'
                    print(f"| ❌ Sin resultados")
            else:
                result['error'] = 'Sin datos'
                print(f"| ❌ Sin datos")
                if 'error' in api_result[0]:
                    result['error'] = api_result[0]['error']
        
        elif response.status_code == 429:
            result['error'] = 'Rate limit'
            print(f"| ⚠️  Rate limit")
            sleep(60)
        
        else:
            result['error'] = f'HTTP {response.status_code}'
            print(f"| ❌ HTTP {response.status_code}")
    
    except Exception as e:
        result['error'] = str(e)
        print(f"| ❌ {str(e)[:30]}")
    
    results.append(result)
    sleep(0.4)  # Pausa entre requests

print("\n" + "="*80)
print("ANÁLISIS DE RESULTADOS")
print("="*80)

successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]

print(f"\n📊 ESTADÍSTICAS GENERALES:")
print(f"   Total MICs probados: {len(results)}")
print(f"   ✅ Éxitos (ticker obtenido): {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
print(f"   ❌ Fallos: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")

if successful:
    # Análisis por tipo de exchange
    exchanges_principales = ['XNAS', 'XNYS', 'XHKG', 'XMAD', 'XPAR', 'XWAR', 'XOSL', 'XSTO', 'XTSE', 'XTSX', 'XAMS', 'XLON', 'MTAA']
    dark_pools = [r for r in successful if r['mic_degiro'] not in exchanges_principales]
    principales = [r for r in successful if r['mic_degiro'] in exchanges_principales]
    
    print(f"\n📈 ÉXITOS POR TIPO:")
    print(f"   Exchanges principales: {len(principales)}/{len([r for r in results if r['mic_degiro'] in exchanges_principales])}")
    print(f"   Dark pools/ATSs: {len(dark_pools)}/{len([r for r in results if r['mic_degiro'] not in exchanges_principales])}")
    
    print(f"\n✅ EJEMPLOS DE ÉXITOS:")
    for r in successful[:15]:
        print(f"   {r['mic_degiro']:8} → {r['ticker']:10} | Exch: {r['exchange_openfigi']:4} | {r['total_results']:2d} res | {r['producto'][:35]}")

if failed:
    print(f"\n❌ FALLOS ({len(failed)}):")
    for r in failed:
        print(f"   {r['mic_degiro']:8} | Error: {r['error']:25} | {r['producto'][:35]}")

# Análisis de variabilidad
if successful:
    exchanges_openfigi = {}
    for r in successful:
        exch = r['exchange_openfigi']
        if exch:
            if exch not in exchanges_openfigi:
                exchanges_openfigi[exch] = []
            exchanges_openfigi[exch].append(r['mic_degiro'])
    
    print(f"\n📋 EXCHANGES DEVUELTOS POR OPENFIGI ({len(exchanges_openfigi)} únicos):")
    for exch in sorted(exchanges_openfigi.keys()):
        mics = set(exchanges_openfigi[exch])
        print(f"   {exch:4} ← {', '.join(sorted(mics)[:10])}")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)

tasa_exito = len(successful)/len(results)*100

print(f"""
📈 TASA DE ÉXITO: {tasa_exito:.1f}%

{'✅ EXCELENTE - ESTRATEGIA VIABLE' if tasa_exito >= 80 else '⚠️ ACEPTABLE - CONSIDERAR MEJORAS' if tasa_exito >= 60 else '❌ INSUFICIENTE - NECESITA OTRA ESTRATEGIA'}

💡 IMPLEMENTACIÓN RECOMENDADA:

def obtener_ticker_openfigi(isin, currency, mic_csv):
    \"\"\"
    Obtiene ticker de OpenFIGI usando estrategia simple
    \"\"\"
    # 1. Consultar OpenFIGI con ISIN + Currency
    result = openfigi.mapping(isin=isin, currency=currency)
    
    # 2. Tomar primer resultado
    if result and len(result) > 0:
        ticker = result[0]['ticker']
        # IMPORTANTE: Guardar MIC original del CSV, NO el de OpenFIGI
        exchange = mic_csv  # Ej: XNAS, XHKG (correcto)
        return ticker, exchange
    
    return None, mic_csv

📝 DATOS A GUARDAR EN BD:
   - symbol: ticker obtenido de OpenFIGI
   - exchange: MIC del CSV DeGiro (columna 5) ← SIEMPRE CORRECTO
   - isin: del CSV
   - currency: del CSV

✅ VENTAJAS:
   - Simple y directo
   - No requiere mapeos
   - Tasa de éxito: {tasa_exito:.1f}%
   - Fácil de mantener

⚠️  LIMITACIÓN:
   - El ticker puede ser de un exchange diferente al del CSV
   - Pero tenemos el MIC correcto del CSV para referencia
""")
print()

