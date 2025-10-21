"""
Test: Probar los FALLOS de la estrategia avanzada con la estrategia SIMPLE
Objetivo: Ver si la estrategia simple resuelve casos que la avanzada no pudo
"""
import json
import requests
from time import sleep

OPENFIGI_URL = 'https://api.openfigi.com/v3/mapping'

print("\n" + "="*80)
print("TEST: FALLOS DE ESTRATEGIA AVANZADA CON ESTRATEGIA SIMPLE")
print("="*80)

# Cargar fallos
try:
    with open('advanced_strategy_failures.json', 'r', encoding='utf-8') as f:
        failures = json.load(f)
except FileNotFoundError:
    print("\n❌ ERROR: Primero ejecuta 'test_advanced_and_save_failures.py'")
    exit(1)

print(f"\n📊 Casos fallidos a probar: {len(failures)}")
print(f"⏱️  Tiempo estimado: {len(failures) * 0.6 / 60:.1f} minutos\n")

headers = {'Content-Type': 'application/json'}
simple_results = []

# Probar cada fallo con estrategia simple
for i, failure in enumerate(failures, 1):
    isin = failure['isin']
    currency = failure['currency']
    producto = failure['producto']
    mic = failure['mic']
    
    print(f"[{i:3d}/{len(failures)}] {isin:15} | {mic:8} | {producto[:30]:30} ", end='', flush=True)
    
    result = {
        'isin': isin,
        'mic': mic,
        'currency': currency,
        'producto': producto,
        'ticker': None,
        'exchange': None,
        'name': None,
        'success': False,
        'total_results': 0
    }
    
    try:
        # ESTRATEGIA SIMPLE: ISIN + Currency, tomar primer resultado
        payload = [{
            'idType': 'ID_ISIN',
            'idValue': isin,
            'currency': currency
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
                    result['exchange'] = first.get('exchCode')
                    result['name'] = first.get('name')
                    result['success'] = True
                    
                    print(f"| ✅ {result['ticker']:10} ({result['exchange']}) [{result['total_results']:2d}]")
                else:
                    print(f"| ❌ Sin resultados")
            else:
                print(f"| ❌ Sin datos")
        
        elif response.status_code == 429:
            print(f"| ⚠️  Rate limit")
            sleep(60)
            continue
        
        else:
            print(f"| ❌ HTTP {response.status_code}")
    
    except Exception as e:
        print(f"| ❌ {str(e)[:30]}")
    
    simple_results.append(result)
    sleep(0.6)

print("\n" + "="*80)
print("ANÁLISIS COMPARATIVO")
print("="*80)

# Estadísticas
simple_success = [r for r in simple_results if r['success']]
simple_failed = [r for r in simple_results if not r['success']]

print(f"\n📊 RESULTADOS DE ESTRATEGIA SIMPLE EN FALLOS DE AVANZADA:")
print(f"   Total casos probados: {len(simple_results)}")
print(f"   ✅ Resueltos ahora: {len(simple_success)} ({len(simple_success)/len(simple_results)*100:.1f}%)")
print(f"   ❌ Siguen sin resolver: {len(simple_failed)} ({len(simple_failed)/len(simple_results)*100:.1f}%)")

# Guardar resultados
with open('simple_strategy_on_failures.json', 'w', encoding='utf-8') as f:
    json.dump(simple_results, f, indent=2, ensure_ascii=False)
print(f"\n💾 Resultados guardados en 'simple_strategy_on_failures.json'")

# Cargar resultados completos de estrategia avanzada para comparación global
with open('advanced_strategy_all_results.json', 'r', encoding='utf-8') as f:
    advanced_all = json.load(f)

advanced_success = [r for r in advanced_all if r['success'] and r['ticker']]
advanced_failed = [r for r in advanced_all if not r['success'] or not r['ticker']]

print("\n" + "="*80)
print("COMPARACIÓN GLOBAL")
print("="*80)

total_cases = len(advanced_all)
advanced_success_count = len(advanced_success)
simple_recovered = len(simple_success)  # Casos que la simple resolvió de los fallos de avanzada

# Tasa de éxito proyectada de estrategia simple
simple_projected_success = advanced_success_count + simple_recovered
simple_projected_rate = simple_projected_success / total_cases * 100
advanced_rate = advanced_success_count / total_cases * 100

print(f"\n📊 ESTRATEGIA AVANZADA:")
print(f"   Éxitos: {advanced_success_count}/{total_cases} ({advanced_rate:.1f}%)")
print(f"   Fallos: {len(advanced_failed)}/{total_cases} ({len(advanced_failed)/total_cases*100:.1f}%)")

print(f"\n📊 ESTRATEGIA SIMPLE (proyectada):")
print(f"   Éxitos estimados: {simple_projected_success}/{total_cases} ({simple_projected_rate:.1f}%)")
print(f"   → Casos que avanzada resolvió: {advanced_success_count}")
print(f"   → Casos adicionales resueltos: {simple_recovered}")
print(f"   Fallos estimados: {len(simple_failed)}/{total_cases} ({len(simple_failed)/total_cases*100:.1f}%)")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)

if simple_recovered > 0:
    print(f"""
✅ LA ESTRATEGIA SIMPLE RESOLVIÓ {simple_recovered} CASOS ADICIONALES
   que la estrategia avanzada NO pudo resolver.

📈 TASAS DE ÉXITO:
   Estrategia Avanzada: {advanced_rate:.1f}%
   Estrategia Simple:   {simple_projected_rate:.1f}%
   
   {'✅ ESTRATEGIA SIMPLE ES SUPERIOR' if simple_projected_rate > advanced_rate else '⚠️ AMBAS SON EQUIVALENTES' if abs(simple_projected_rate - advanced_rate) < 1 else '❌ ESTRATEGIA AVANZADA ES SUPERIOR'}

💡 RECOMENDACIÓN:
   {'Usar ESTRATEGIA SIMPLE' if simple_projected_rate >= advanced_rate else 'Usar ESTRATEGIA AVANZADA'}
   - Más {'simple' if simple_projected_rate >= advanced_rate else 'compleja'}
   - {'Mayor' if simple_projected_rate > advanced_rate else 'Menor' if simple_projected_rate < advanced_rate else 'Igual'} tasa de éxito
   - {'Menos' if simple_projected_rate >= advanced_rate else 'Más'} código a mantener
""")
else:
    print(f"""
❌ LA ESTRATEGIA SIMPLE NO RESOLVIÓ NINGÚN CASO ADICIONAL

📈 TASAS DE ÉXITO:
   Estrategia Avanzada: {advanced_rate:.1f}%
   Estrategia Simple:   {simple_projected_rate:.1f}% (igual)

💡 RECOMENDACIÓN:
   Usar ESTRATEGIA SIMPLE de todas formas:
   - Igual tasa de éxito
   - Mucho más simple
   - Menos código a mantener
""")

# Mostrar casos que ambas fallaron
if simple_failed:
    print(f"\n❌ CASOS QUE AMBAS ESTRATEGIAS FALLARON ({len(simple_failed)}):")
    for r in simple_failed[:10]:
        print(f"   {r['isin']:15} | {r['mic']:8} ({r['currency']}) | {r['producto'][:40]}")
    
    if len(simple_failed) > 10:
        print(f"   ... y {len(simple_failed) - 10} más")

print()

