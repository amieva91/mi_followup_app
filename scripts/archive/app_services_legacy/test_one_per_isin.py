"""
Test: 1 caso por ISIN único
Más representativo y rápido (~2 minutos)
"""
import csv
import requests
import json
from time import sleep

OPENFIGI_URL = 'https://api.openfigi.com/v3/mapping'

print("\n" + "="*80)
print("TEST: 1 CASO POR ISIN ÚNICO")
print("="*80)

# Recopilar 1 caso por ISIN
csv_path = "uploads/TransaccionesDegiro.csv"
isin_cases = {}

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    
    for row in reader:
        if len(row) > 8:
            isin = row[3].strip()
            mic = row[5].strip()
            currency = row[8].strip() or 'EUR'
            producto = row[2].strip()
            
            # Guardar solo el primer caso por ISIN
            if isin and mic and isin not in isin_cases:
                isin_cases[isin] = {
                    'isin': isin,
                    'mic': mic,
                    'currency': currency,
                    'producto': producto
                }

cases = list(isin_cases.values())

print(f"\n📊 Total ISINs únicos: {len(cases)}")
print(f"⏱️  Tiempo estimado: {len(cases) * 0.6 / 60:.1f} minutos\n")

headers = {'Content-Type': 'application/json'}
results = []

# Procesar
for i, case in enumerate(cases, 1):
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
                result['error'] = 'Sin datos'
                print(f"| ❌ Sin datos")
        
        elif response.status_code == 429:
            result['error'] = 'Rate limit'
            print(f"| ⚠️  Rate limit")
            sleep(60)
            continue
        
        else:
            result['error'] = f'HTTP {response.status_code}'
            print(f"| ❌ HTTP {response.status_code}")
    
    except Exception as e:
        result['error'] = str(e)[:50]
        print(f"| ❌ {result['error'][:30]}")
    
    results.append(result)
    sleep(0.6)

print("\n" + "="*80)
print("ANÁLISIS FINAL")
print("="*80)

successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]

print(f"\n📊 ESTADÍSTICAS FINALES:")
print(f"   Total ISINs probados: {len(results)}")
print(f"   ✅ Éxitos: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
print(f"   ❌ Fallos: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")

# Por moneda
print(f"\n📈 ÉXITOS POR MONEDA:")
success_by_curr = {}
for r in successful:
    curr = r['currency']
    success_by_curr[curr] = success_by_curr.get(curr, 0) + 1

for curr in sorted(success_by_curr.keys()):
    total_curr = sum(1 for r in results if r['currency'] == curr)
    print(f"   {curr}: {success_by_curr[curr]}/{total_curr} ({success_by_curr[curr]/total_curr*100:.1f}%)")

print(f"\n❌ FALLOS POR MONEDA:")
fails_by_curr = {}
for r in failed:
    curr = r['currency']
    if curr not in fails_by_curr:
        fails_by_curr[curr] = []
    fails_by_curr[curr].append(r)

for curr in sorted(fails_by_curr.keys()):
    casos = fails_by_curr[curr]
    print(f"   {curr}: {len(casos)} fallo(s)")
    for caso in casos[:3]:
        print(f"      - {caso['mic']:8} | {caso['producto'][:40]}")

# Análisis de exchanges
print(f"\n📊 EXCHANGES MÁS COMUNES (OpenFIGI):")
exchange_counts = {}
for r in successful:
    exch = r['exchange_openfigi']
    if exch:
        exchange_counts[exch] = exchange_counts.get(exch, 0) + 1

for exch, count in sorted(exchange_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"   {exch:4} : {count:3d} casos")

# Listar TODOS los fallos
if failed:
    print(f"\n❌ LISTA COMPLETA DE FALLOS ({len(failed)}):")
    for r in failed:
        print(f"   {r['isin']:15} | {r['mic']:8} ({r['currency']}) | {r['producto'][:40]}")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)

tasa_exito = len(successful)/len(results)*100

print(f"""
📈 TASA DE ÉXITO: {tasa_exito:.1f}%

{'✅ EXCELENTE - Estrategia perfectamente viable (≥85%)' if tasa_exito >= 85 else '✅ BUENA - Estrategia viable (75-85%)' if tasa_exito >= 75 else '⚠️ ACEPTABLE - Considerar mejoras (60-75%)' if tasa_exito >= 60 else '❌ INSUFICIENTE (<60%)'}

💡 DECISIÓN:
   Con {len(results)} ISINs únicos probados, la estrategia simple de
   consultar OpenFIGI con ISIN + Currency tiene {tasa_exito:.1f}% de éxito.
   
   {'✅ RECOMENDACIÓN: IMPLEMENTAR esta estrategia' if tasa_exito >= 80 else '⚠️ RECOMENDACIÓN: Considerar estrategia híbrida' if tasa_exito >= 70 else '❌ RECOMENDACIÓN: Buscar alternativas'}
   
   Para los {len(failed)} activos sin ticker ({len(failed)/len(results)*100:.1f}%):
   - Dejar sin ticker (no es crítico para funcionamiento)
   - El MIC del CSV (columna 5) se guarda siempre
   - Se puede intentar resolución manual si es necesario

📝 PRÓXIMOS PASOS:
   1. Modificar parser DeGiro para extraer exchange (columna 5)
   2. Crear script de enriquecimiento con esta estrategia
   3. Actualizar assets en BD con ticker + exchange
""")
print()

