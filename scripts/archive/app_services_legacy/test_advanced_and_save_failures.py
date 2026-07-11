"""
Test del resolver avanzado y guardar los fallos para análisis posterior
"""
import csv
import requests
import json
from time import sleep
from typing import Optional, Dict, List

class AdvancedISINResolver:
    """
    Resuelve ISIN + MIC específico a Ticker + Exchange
    Con múltiples estrategias y fallbacks
    """
    
    def __init__(self, rate_limit_delay=0.6):
        self.rate_limit_delay = rate_limit_delay
        self.openfigi_url = 'https://api.openfigi.com/v3/mapping'
    
    def resolve_batch(self, isin_mic_currency_list: List[tuple]) -> List[Dict]:
        """
        Resuelve [(isin1, mic1, currency1, producto1), ...]
        """
        results = []
        
        # Agrupar por ISIN
        isin_groups = {}
        for isin, mic, currency, producto in isin_mic_currency_list:
            if isin not in isin_groups:
                isin_groups[isin] = []
            isin_groups[isin].append({'mic': mic, 'currency': currency, 'producto': producto})
        
        total = len(isin_groups)
        for idx, (isin, mic_data_list) in enumerate(isin_groups.items(), 1):
            # Usar primer producto como referencia
            producto_ref = mic_data_list[0]['producto']
            print(f"[{idx:3d}/{total}] {isin:15} | {producto_ref[:30]:30} ", end='', flush=True)
            
            isin_results = self._resolve_isin_all_mics(isin, mic_data_list)
            results.extend(isin_results)
            
            # Mostrar resumen
            success = sum(1 for r in isin_results if r['ticker'])
            print(f"| {'✅' if success == len(isin_results) else '⚠️' if success > 0 else '❌'} {success}/{len(isin_results)}")
            
            sleep(self.rate_limit_delay)
        
        return results
    
    def _resolve_isin_all_mics(self, isin: str, mic_data_list: List[Dict]) -> List[Dict]:
        """Resuelve un ISIN para múltiples MICs"""
        results = []
        
        # Obtener currency principal
        main_currency = mic_data_list[0]['currency']
        
        # Consultar con currency específica
        all_mappings = self._query_with_currency(isin, main_currency)
        
        if not all_mappings:
            # Fallback: consultar sin currency
            all_mappings = self._query_basic(isin)
        
        # Procesar cada MIC solicitado
        for mic_data in mic_data_list:
            mic = mic_data['mic']
            currency = mic_data['currency']
            producto = mic_data['producto']
            
            if all_mappings:
                # Buscar match exacto por micCode
                best_match = None
                for mapping in all_mappings:
                    if mapping.get('micCode') == mic:
                        best_match = mapping
                        break
                
                if not best_match:
                    # Fallback al primer resultado
                    best_match = all_mappings[0]
                
                results.append({
                    'isin': isin,
                    'mic': mic,
                    'currency': currency,
                    'producto': producto,
                    'ticker': best_match.get('ticker'),
                    'exchange': best_match.get('exchCode'),
                    'name': best_match.get('name'),
                    'success': True
                })
            else:
                # Sin resultados
                results.append({
                    'isin': isin,
                    'mic': mic,
                    'currency': currency,
                    'producto': producto,
                    'ticker': None,
                    'exchange': None,
                    'name': None,
                    'success': False
                })
        
        return results
    
    def _query_with_currency(self, isin: str, currency: str) -> List[Dict]:
        """Consulta con ISIN + Currency"""
        query = {'idType': 'ID_ISIN', 'idValue': isin, 'currency': currency}
        return self._query_openfigi(query)
    
    def _query_basic(self, isin: str) -> List[Dict]:
        """Consulta básica solo con ISIN"""
        query = {'idType': 'ID_ISIN', 'idValue': isin}
        return self._query_openfigi(query)
    
    def _query_openfigi(self, query: Dict) -> List[Dict]:
        """Ejecuta query a OpenFIGI"""
        try:
            response = requests.post(
                self.openfigi_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps([query]),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    if 'data' in data[0]:
                        return data[0]['data']
            elif response.status_code == 429:
                print(" [RATE_LIMIT] ", end='', flush=True)
                sleep(60)
                return self._query_openfigi(query)
        except Exception as e:
            pass
        
        return []


# Script principal
print("\n" + "="*80)
print("TEST ESTRATEGIA AVANZADA - GUARDANDO FALLOS")
print("="*80)

# Leer CSV
csv_path = "uploads/TransaccionesDegiro.csv"
isin_mic_currency_data = []
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
                isin_mic_currency_data.append((isin, mic, currency, producto))

print(f"\n📊 Total casos únicos (ISIN + MIC): {len(isin_mic_currency_data)}")
print(f"⏱️  Tiempo estimado: {len(isin_mic_currency_data) * 0.6 / 60:.1f} minutos\n")

# Resolver
resolver = AdvancedISINResolver(rate_limit_delay=0.6)
results = resolver.resolve_batch(isin_mic_currency_data)

print("\n" + "="*80)
print("ANÁLISIS DE RESULTADOS")
print("="*80)

# Estadísticas
total = len(results)
successful = [r for r in results if r['success'] and r['ticker']]
failed = [r for r in results if not r['success'] or not r['ticker']]

print(f"\n📊 ESTADÍSTICAS:")
print(f"   Total casos: {total}")
print(f"   ✅ Éxitos: {len(successful)} ({len(successful)/total*100:.1f}%)")
print(f"   ❌ Fallos: {len(failed)} ({len(failed)/total*100:.1f}%)")

# Guardar TODOS los resultados
with open('advanced_strategy_all_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n💾 Todos los resultados guardados en 'advanced_strategy_all_results.json'")

# Guardar solo FALLOS
with open('advanced_strategy_failures.json', 'w', encoding='utf-8') as f:
    json.dump(failed, f, indent=2, ensure_ascii=False)
print(f"💾 {len(failed)} fallos guardados en 'advanced_strategy_failures.json'")

# Mostrar fallos
if failed:
    print(f"\n❌ CASOS QUE FALLARON ({len(failed)}):")
    for r in failed[:20]:
        print(f"   {r['isin']:15} | {r['mic']:8} ({r['currency']}) | {r['producto'][:40]}")
    
    if len(failed) > 20:
        print(f"   ... y {len(failed) - 20} más")

print("\n" + "="*80)
print("PRÓXIMO PASO")
print("="*80)
print("""
✅ Resultados guardados

🔜 Ahora ejecutar: test_failures_with_simple_strategy.py
   → Probará SOLO los fallos con la estrategia simple
   → Comparación directa de qué estrategia es mejor
""")
print()

