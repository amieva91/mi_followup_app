"""
Test de estrategia avanzada con OUTPUT DETALLADO
Muestra exactamente qué devuelve OpenFIGI para cada caso
"""
import csv
import requests
import json
from time import sleep
from typing import List, Dict

OPENFIGI_URL = 'https://api.openfigi.com/v3/mapping'

def query_openfigi(isin: str, currency: str) -> List[Dict]:
    """Consulta OpenFIGI con ISIN + Currency"""
    try:
        payload = [{
            'idType': 'ID_ISIN',
            'idValue': isin,
            'currency': currency
        }]
        
        response = requests.post(
            OPENFIGI_URL,
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and 'data' in data[0]:
                return data[0]['data']
        elif response.status_code == 429:
            print(" [RATE_LIMIT - esperando 60s] ", end='', flush=True)
            sleep(60)
            return query_openfigi(isin, currency)
    except Exception as e:
        print(f" [ERROR: {str(e)[:30]}] ", end='', flush=True)
    
    return []

print("\n" + "="*80)
print("TEST DETALLADO: ¿QUÉ DEVUELVE OPENFIGI?")
print("="*80)

# Leer CSV - tomar solo 1 caso por ISIN (primeros 20)
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
                
                # Solo primeros 20 para no saturar
                if len(isin_cases) >= 20:
                    break

cases = list(isin_cases.values())

print(f"\n📊 Casos a probar: {len(cases)}")
print(f"⏱️  Tiempo estimado: {len(cases) * 0.8 / 60:.1f} minutos\n")

all_results = []

for i, case in enumerate(cases, 1):
    isin = case['isin']
    mic = case['mic']
    currency = case['currency']
    producto = case['producto']
    
    print("\n" + "-"*80)
    print(f"[{i:2d}/{len(cases)}] {producto}")
    print(f"         ISIN: {isin} | MIC: {mic} | Currency: {currency}")
    print("-"*80)
    
    # Consultar OpenFIGI
    mappings = query_openfigi(isin, currency)
    
    if not mappings:
        print("❌ SIN RESULTADOS")
        all_results.append({
            'isin': isin,
            'mic': mic,
            'producto': producto,
            'results_count': 0,
            'results': []
        })
        continue
    
    print(f"\n✅ OPENFIGI DEVOLVIÓ {len(mappings)} RESULTADO(S):\n")
    
    result_entry = {
        'isin': isin,
        'mic': mic,
        'producto': producto,
        'results_count': len(mappings),
        'results': []
    }
    
    # Mostrar cada resultado
    for idx, mapping in enumerate(mappings, 1):
        ticker = mapping.get('ticker', 'N/A')
        name = mapping.get('name', 'N/A')
        exchCode = mapping.get('exchCode', 'N/A')
        micCode = mapping.get('micCode', 'N/A')
        currency_figi = mapping.get('currency', 'N/A')
        securityType = mapping.get('securityType', 'N/A')
        marketSector = mapping.get('marketSector', 'N/A')
        
        match_status = ""
        if micCode == mic:
            match_status = " 🎯 MATCH EXACTO POR MIC"
        elif exchCode == mic:
            match_status = " 🎯 MATCH EXACTO POR EXCHCODE"
        
        print(f"   [{idx}] Ticker: {ticker:12} | Exchange: {exchCode:6} | MIC: {micCode:8}{match_status}")
        print(f"       Name: {name[:60]}")
        print(f"       Currency: {currency_figi:4} | Type: {securityType:12} | Sector: {marketSector}")
        
        result_entry['results'].append({
            'ticker': ticker,
            'name': name,
            'exchCode': exchCode,
            'micCode': micCode,
            'currency': currency_figi,
            'securityType': securityType,
            'marketSector': marketSector,
            'is_exact_match': micCode == mic or exchCode == mic
        })
    
    all_results.append(result_entry)
    sleep(0.8)

print("\n" + "="*80)
print("RESUMEN DE ANÁLISIS")
print("="*80)

total_with_results = sum(1 for r in all_results if r['results_count'] > 0)
total_without_results = len(all_results) - total_with_results
total_exact_matches = sum(1 for r in all_results if any(res['is_exact_match'] for res in r['results']))

print(f"\n📊 ESTADÍSTICAS:")
print(f"   Total casos probados: {len(all_results)}")
print(f"   ✅ Con resultados: {total_with_results} ({total_with_results/len(all_results)*100:.1f}%)")
print(f"   ❌ Sin resultados: {total_without_results} ({total_without_results/len(all_results)*100:.1f}%)")
print(f"   🎯 Con match EXACTO de MIC: {total_exact_matches} ({total_exact_matches/len(all_results)*100:.1f}%)")

# Análisis de multiplicidad de resultados
print(f"\n📊 CANTIDAD DE RESULTADOS POR CASO:")
result_counts = {}
for r in all_results:
    count = r['results_count']
    result_counts[count] = result_counts.get(count, 0) + 1

for count in sorted(result_counts.keys()):
    print(f"   {count:3d} resultado(s): {result_counts[count]:3d} casos")

# Guardar resultados completos
with open('openfigi_detailed_results.json', 'w', encoding='utf-8') as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)

print(f"\n💾 Resultados detallados guardados en 'openfigi_detailed_results.json'")

print("\n" + "="*80)
print("OBSERVACIONES CLAVE")
print("="*80)

print(f"""
📊 HALLAZGOS:
   - OpenFIGI devuelve múltiples resultados para muchos ISINs
   - Cada ISIN puede cotizar en múltiples exchanges
   - El MIC de DeGiro no siempre coincide con micCode o exchCode de OpenFIGI
   
🎯 MATCH EXACTO DE MIC:
   - Solo {total_exact_matches}/{len(all_results)} casos ({total_exact_matches/len(all_results)*100:.1f}%) tienen match exacto
   - Esto significa que para {len(all_results) - total_exact_matches} casos, hay que elegir un resultado
   
💡 ESTRATEGIA SIMPLE:
   - Tomar el primer resultado cuando no hay match exacto
   - Es más simple y probablemente igual de efectivo
   - El MIC de DeGiro se guarda de todos modos (columna 5 del CSV)

📝 CAMPOS DISPONIBLES:
   - ticker: El símbolo bursátil
   - name: Nombre completo del activo
   - exchCode: Código del exchange (interno de OpenFIGI)
   - micCode: Código MIC estándar ISO 10383
   - currency: Moneda de cotización
   - securityType: Tipo de valor (Common Stock, ETF, etc.)
   - marketSector: Sector de mercado (Equity, etc.)
""")

print()

