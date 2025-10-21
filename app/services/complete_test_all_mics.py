"""
Test COMPLETO con TODOS los casos únicos ISIN+MIC del CSV DeGiro
Con guardado incremental de resultados
"""
import csv
import requests
import json
from time import sleep
import os
import pickle

OPENFIGI_URL = 'https://api.openfigi.com/v3/mapping'
RESULTS_FILE = 'app/services/complete_results.pkl'

print("\n" + "="*80)
print("TEST COMPLETO: TODOS LOS CASOS ISIN + MIC DE DEGIRO")
print("="*80)

# Recopilar TODOS los casos únicos ISIN+MIC
csv_path = "uploads/TransaccionesDegiro.csv"
cases = []
seen = set()

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    
    for row in reader:
        if len(row) > 8:
            isin = row[3].strip()
            mic = row[5].strip()
            currency = row[8].strip() or 'EUR'
            producto = row[2].strip()
            
            key = f"{isin}|{mic}"
            if key not in seen and isin and mic:
                seen.add(key)
                cases.append({
                    'isin': isin,
                    'mic': mic,
                    'currency': currency,
                    'producto': producto
                })

print(f"\n📊 Total casos únicos (ISIN + MIC): {len(cases)}")

# Cargar resultados previos si existen
results = []
processed_keys = set()

if os.path.exists(RESULTS_FILE):
    try:
        with open(RESULTS_FILE, 'rb') as f:
            results = pickle.load(f)
        processed_keys = {f"{r['isin']}|{r['mic']}" for r in results}
        print(f"📂 Cargados {len(results)} resultados previos")
    except:
        print("⚠️  No se pudieron cargar resultados previos")

# Filtrar casos ya procesados
pending_cases = [c for c in cases if f"{c['isin']}|{c['mic']}" not in processed_keys]

if not pending_cases:
    print("✅ Todos los casos ya fueron procesados")
else:
    print(f"📋 Pendientes de procesar: {len(pending_cases)}/{len(cases)}")
    print(f"⏱️  Tiempo estimado: {len(pending_cases) * 0.6 / 60:.1f} minutos\n")

headers = {'Content-Type': 'application/json'}

# Procesar casos pendientes
for idx, case in enumerate(pending_cases):
    i = len(results) + 1
    print(f"[{i:3d}/{len(cases)}] {case['isin']:15} | {case['mic']:8} | {case['producto'][:30]:30} ", end='', flush=True)
    
    result = {
        'isin': case['isin'],
        'mic': case['mic'],
        'currency': case['currency'],
        'producto': case['producto'],
        'ticker': None,
        'exchange_openfigi': None,
        'name': None,
        'total_results': 0,
        'success': False,
        'error': None
    }
    
    try:
        # Consultar OpenFIGI: ISIN + Currency
        payload = [{
            'idType': 'ID_ISIN',
            'idValue': case['isin'],
            'currency': case['currency']
        }]
        
        response = requests.post(OPENFIGI_URL, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and len(data) > 0 and 'data' in data[0]:
                items = data[0]['data']
                result['total_results'] = len(items)
                
                if items:
                    first = items[0]
                    result['ticker'] = first.get('ticker')
                    result['exchange_openfigi'] = first.get('exchCode')
                    result['name'] = first.get('name')
                    result['success'] = True
                    
                    print(f"| ✅ {result['ticker']:10} ({result['exchange_openfigi']}) [{result['total_results']:2d}]")
                else:
                    result['error'] = 'Sin resultados'
                    print(f"| ❌ Sin resultados")
            else:
                result['error'] = 'Sin datos en respuesta'
                print(f"| ❌ Sin datos")
        
        elif response.status_code == 429:
            result['error'] = 'Rate limit'
            print(f"| ⚠️  Rate limit - Pausa 60s")
            sleep(60)
            # No agregar a results, reintentar
            continue
        
        else:
            result['error'] = f'HTTP {response.status_code}'
            print(f"| ❌ HTTP {response.status_code}")
    
    except Exception as e:
        result['error'] = str(e)[:50]
        print(f"| ❌ {result['error']}")
    
    results.append(result)
    
    # Guardar cada 10 resultados
    if len(results) % 10 == 0:
        with open(RESULTS_FILE, 'wb') as f:
            pickle.dump(results, f)
    
    sleep(0.6)

# Guardar resultados finales
with open(RESULTS_FILE, 'wb') as f:
    pickle.dump(results, f)

print("\n" + "="*80)
print("ANÁLISIS COMPLETO DE RESULTADOS")
print("="*80)

successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]

print(f"\n📊 ESTADÍSTICAS FINALES:")
print(f"   Total casos: {len(results)}")
print(f"   ✅ Éxitos: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
print(f"   ❌ Fallos: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")

# Análisis por moneda
print(f"\n📈 ÉXITOS POR MONEDA:")
success_by_currency = {}
for r in successful:
    curr = r['currency']
    if curr not in success_by_currency:
        success_by_currency[curr] = 0
    success_by_currency[curr] += 1

for curr in sorted(success_by_currency.keys()):
    count = success_by_currency[curr]
    print(f"   {curr}: {count} éxito(s)")

print(f"\n📉 FALLOS POR MONEDA:")
fails_by_currency = {}
for r in failed:
    curr = r['currency']
    if curr not in fails_by_currency:
        fails_by_currency[curr] = []
    fails_by_currency[curr].append(r)

for curr in sorted(fails_by_currency.keys()):
    casos = fails_by_currency[curr]
    print(f"   {curr}: {len(casos)} fallo(s)")
    # Mostrar hasta 3 ejemplos
    for caso in casos[:3]:
        print(f"      - {caso['mic']:8} | {caso['producto'][:35]}")

# Análisis de MICs
print(f"\n📊 ÉXITOS POR TIPO DE MIC:")
exchanges_principales = ['XNAS', 'XNYS', 'XHKG', 'XMAD', 'XPAR', 'XWAR', 'XOSL', 'XSTO', 'XTSE', 'XTSX', 'XAMS', 'XLON', 'MTAA']

principales_exitosos = [r for r in successful if r['mic'] in exchanges_principales]
principales_totales = [r for r in results if r['mic'] in exchanges_principales]

dark_exitosos = [r for r in successful if r['mic'] not in exchanges_principales]
dark_totales = [r for r in results if r['mic'] not in exchanges_principales]

print(f"   Exchanges principales: {len(principales_exitosos)}/{len(principales_totales)} ({len(principales_exitosos)/len(principales_totales)*100:.1f}%)")
print(f"   Dark pools/ATSs: {len(dark_exitosos)}/{len(dark_totales)} ({len(dark_exitosos)/len(dark_totales)*100:.1f}%)")

# Exchanges devueltos por OpenFIGI
print(f"\n📋 EXCHANGES DEVUELTOS POR OPENFIGI:")
exchange_counts = {}
for r in successful:
    exch = r['exchange_openfigi']
    if exch:
        if exch not in exchange_counts:
            exchange_counts[exch] = 0
        exchange_counts[exch] += 1

for exch in sorted(exchange_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"   {exch[0]:4} : {exch[1]:3d} casos")

print(f"\n❌ TODOS LOS FALLOS ({len(failed)}):")
for r in failed:
    print(f"   {r['isin']:15} | {r['mic']:8} ({r['currency']}) | {r['error']:25} | {r['producto'][:30]}")

print("\n" + "="*80)
print("CONCLUSIÓN FINAL")
print("="*80)

tasa_exito = len(successful)/len(results)*100

print(f"""
📈 TASA DE ÉXITO FINAL: {tasa_exito:.1f}%

{'✅ EXCELENTE - Estrategia perfectamente viable' if tasa_exito >= 85 else '✅ BUENA - Estrategia viable' if tasa_exito >= 75 else '⚠️ ACEPTABLE - Considerar mejoras' if tasa_exito >= 60 else '❌ INSUFICIENTE'}

💡 CONCLUSIÓN:
   Con {len(results)} casos únicos probados, la estrategia simple de
   ISIN + Currency → Primer resultado tiene {tasa_exito:.1f}% de éxito.
   
   Esto es {'SUFICIENTE' if tasa_exito >= 80 else 'ACEPTABLE' if tasa_exito >= 70 else 'INSUFICIENTE'} para implementar en producción.
   
   Para los {len(failed)} casos fallidos ({len(failed)/len(results)*100:.1f}%):
   - Pueden dejarse sin ticker (no crítico)
   - Guardar el MIC del CSV (columna 5) que siempre es correcto
   - Intentar resolución manual si es necesario

✅ Resultados guardados en: {RESULTS_FILE}
""")
print()

