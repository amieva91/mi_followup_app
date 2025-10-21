"""
Simulación COMPLETA: ISIN + Currency → Primer resultado
Todos los MICs de DeGiro con pausas para evitar rate limit
"""
import csv
import requests
import json
from time import sleep
import pickle
import os

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
RESULTS_FILE = "app/services/openfigi_results.pkl"

csv_path = "uploads/TransaccionesDegiro.csv"

print("\n" + "="*80)
print("SIMULACIÓN COMPLETA: ESTRATEGIA SIMPLE (ISIN + CURRENCY)")
print("="*80)

# Recopilar todos los MICs únicos
mic_examples = {}

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    
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

# Cargar resultados previos si existen
results = []
start_index = 0

if os.path.exists(RESULTS_FILE):
    try:
        with open(RESULTS_FILE, 'rb') as f:
            results = pickle.load(f)
        start_index = len(results)
        print(f"📂 Cargados {start_index} resultados previos")
    except:
        print("⚠️  No se pudieron cargar resultados previos, empezando desde 0")

print(f"📊 Total MICs: {len(test_cases)}")
print(f"📋 Procesando desde {start_index + 1} hasta {len(test_cases)}...\n")

headers = {'Content-Type': 'application/json'}

for i in range(start_index, len(test_cases)):
    test = test_cases[i]
    
    print(f"[{i+1:2d}/{len(test_cases)}] {test['mic_degiro']:8} | {test['producto'][:40]:40} ", end='', flush=True)
    
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
        
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=15)
        
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
            print(f"| ⚠️  Rate limit - Pausando 60s...")
            sleep(60)
            # Reintentar
            continue
        
        else:
            result['error'] = f'HTTP {response.status_code}'
            print(f"| ❌ HTTP {response.status_code}")
    
    except Exception as e:
        result['error'] = str(e)
        print(f"| ❌ {str(e)[:30]}")
    
    results.append(result)
    
    # Guardar progreso cada 5 resultados
    if (i + 1) % 5 == 0:
        with open(RESULTS_FILE, 'wb') as f:
            pickle.dump(results, f)
    
    sleep(0.6)  # Pausa más larga

# Guardar resultados finales
with open(RESULTS_FILE, 'wb') as f:
    pickle.dump(results, f)

print("\n" + "="*80)
print("ANÁLISIS COMPLETO DE RESULTADOS")
print("="*80)

successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]

print(f"\n📊 ESTADÍSTICAS FINALES:")
print(f"   Total MICs probados: {len(results)}")
print(f"   ✅ Éxitos (ticker obtenido): {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
print(f"   ❌ Fallos: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")

# Análisis por tipo de exchange
exchanges_principales = ['XNAS', 'XNYS', 'XHKG', 'XMAD', 'XPAR', 'XWAR', 'XOSL', 'XSTO', 'XTSE', 'XTSX', 'XAMS', 'XLON', 'MTAA', 'XETR', 'XFRA']

principales_exitosos = [r for r in successful if r['mic_degiro'] in exchanges_principales]
principales_totales = [r for r in results if r['mic_degiro'] in exchanges_principales]

dark_pools_exitosos = [r for r in successful if r['mic_degiro'] not in exchanges_principales]
dark_pools_totales = [r for r in results if r['mic_degiro'] not in exchanges_principales]

print(f"\n📈 ÉXITOS POR CATEGORÍA:")
print(f"   Exchanges principales: {len(principales_exitosos)}/{len(principales_totales)} ({len(principales_exitosos)/len(principales_totales)*100:.1f}%)")
print(f"   Dark pools/ATSs: {len(dark_pools_exitosos)}/{len(dark_pools_totales)} ({len(dark_pools_exitosos)/len(dark_pools_totales)*100:.1f}%)")

# Análisis por moneda
fallos_por_moneda = {}
for r in failed:
    currency = r['currency']
    if currency not in fallos_por_moneda:
        fallos_por_moneda[currency] = []
    fallos_por_moneda[currency].append(r)

if fallos_por_moneda:
    print(f"\n❌ FALLOS POR MONEDA:")
    for currency in sorted(fallos_por_moneda.keys()):
        casos = fallos_por_moneda[currency]
        print(f"   {currency}: {len(casos)} fallo(s)")
        for r in casos[:3]:  # Primeros 3 ejemplos
            print(f"      - {r['mic_degiro']:8} | {r['producto'][:35]}")

print(f"\n❌ TODOS LOS FALLOS ({len(failed)}):")
for r in failed:
    print(f"   {r['mic_degiro']:8} ({r['currency']}) | {r['error']:20} | {r['producto'][:35]}")

# Análisis de exchanges OpenFIGI
if successful:
    exchanges_openfigi = {}
    for r in successful:
        exch = r['exchange_openfigi']
        if exch:
            if exch not in exchanges_openfigi:
                exchanges_openfigi[exch] = {'count': 0, 'mics': set()}
            exchanges_openfigi[exch]['count'] += 1
            exchanges_openfigi[exch]['mics'].add(r['mic_degiro'])
    
    print(f"\n📋 EXCHANGES DEVUELTOS POR OPENFIGI:")
    for exch in sorted(exchanges_openfigi.keys(), key=lambda x: exchanges_openfigi[x]['count'], reverse=True):
        data = exchanges_openfigi[exch]
        mics_str = ', '.join(sorted(data['mics'])[:8])
        if len(data['mics']) > 8:
            mics_str += f", +{len(data['mics'])-8} más"
        print(f"   {exch:4} ({data['count']:2d}) ← {mics_str}")

print("\n" + "="*80)
print("CONCLUSIÓN FINAL")
print("="*80)

tasa_exito = len(successful)/len(results)*100

print(f"""
📈 TASA DE ÉXITO FINAL: {tasa_exito:.1f}%

{'✅ EXCELENTE - ESTRATEGIA PERFECTAMENTE VIABLE' if tasa_exito >= 85 else '✅ BUENA - ESTRATEGIA VIABLE' if tasa_exito >= 75 else '⚠️ ACEPTABLE - CONSIDERAR MEJORAS' if tasa_exito >= 60 else '❌ INSUFICIENTE'}

💡 RECOMENDACIÓN:
   {'Esta estrategia es suficiente para el 85%+ de los casos.' if tasa_exito >= 85 else 'Esta estrategia cubre la mayoría de casos.' if tasa_exito >= 75 else 'Considerar estrategia híbrida.'}
   Para los fallos, podemos:
   1. Dejarlos sin ticker (no crítico)
   2. Intentar conversiones de moneda (GBX → GBP)
   3. Buscar manualmente los casos problemáticos
""")
print()

