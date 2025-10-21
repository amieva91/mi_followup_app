"""
Test del resolver ULTRA avanzado con datos reales de DeGiro
Incluye: match exacto de MIC, fallback inteligente, variantes de moneda
"""
import csv
import requests
import json
from time import sleep
from typing import Optional, Dict, List

class UltraAdvancedISINResolver:
    """
    Resuelve ISIN + MIC específico a Ticker + Exchange
    Con múltiples estrategias y fallbacks inteligentes
    """
    
    def __init__(self, rate_limit_delay=0.5):
        self.rate_limit_delay = rate_limit_delay
        self.openfigi_url = 'https://api.openfigi.com/v3/mapping'
        
        # MICs consolidados vs específicos (US tiene muchos sub-MICs)
        self.mic_relationships = {
            'US': ['XNYS', 'XNAS', 'ARCX', 'BATS', 'CDED', 'SOHO', 'MEMX', 
                   'MSPL', 'EDGX', 'EDGA', 'EPRL', 'XBOS', 'IEXG', 'MSCO',
                   'XCIS', 'XPSX', 'BATY'],
        }
        
        # Variantes de moneda por país
        self.country_currencies = {
            'GB': ['GBP', 'GBX', 'GBp'],
            'ZA': ['ZAR', 'ZAC'],
            'US': ['USD'],
            'EU': ['EUR'], 'DE': ['EUR'], 'FR': ['EUR'], 'IT': ['EUR'],
            'ES': ['EUR'], 'NL': ['EUR'], 'BE': ['EUR'], 'AT': ['EUR'],
            'PT': ['EUR'], 'IE': ['EUR'], 'FI': ['EUR'], 'GR': ['EUR'],
            'LU': ['EUR'], 'BG': ['EUR'],
            'HK': ['HKD'], 'KY': ['HKD'], 'BM': ['HKD'],
            'VG': ['USD'], 'MH': ['USD'],
            'AU': ['AUD'], 'CA': ['CAD'], 'PL': ['PLN'],
            'SE': ['SEK'], 'NO': ['NOK'], 'DK': ['DKK'],
        }
    
    def resolve_batch(self, isin_mic_currency_list: List[tuple]) -> List[Dict]:
        """
        Resuelve [(isin1, mic1, currency1), ...]
        """
        results = []
        
        # Agrupar por ISIN
        isin_groups = {}
        for isin, mic, currency in isin_mic_currency_list:
            if isin not in isin_groups:
                isin_groups[isin] = []
            isin_groups[isin].append({'mic': mic, 'currency': currency})
        
        total = len(isin_groups)
        for idx, (isin, mic_data_list) in enumerate(isin_groups.items(), 1):
            print(f"[{idx:2d}/{total}] {isin:15} ", end='', flush=True)
            
            isin_results = self._resolve_isin_all_mics(isin, mic_data_list)
            results.extend(isin_results)
            
            # Mostrar resumen
            success = sum(1 for r in isin_results if r['ticker'])
            exact = sum(1 for r in isin_results if r['match_type'] == 'exact')
            print(f"| {success}/{len(isin_results)} [{exact} exact]")
            
            sleep(self.rate_limit_delay)
        
        return results
    
    def _resolve_isin_all_mics(self, isin: str, mic_data_list: List[Dict]) -> List[Dict]:
        """Resuelve un ISIN para múltiples MICs usando estrategias avanzadas"""
        results = []
        
        # Obtener currency principal
        main_currency = mic_data_list[0]['currency']
        
        # ESTRATEGIA 1: Consultar con currency específica
        all_mappings = self._query_with_currency(isin, main_currency)
        
        if not all_mappings:
            # ESTRATEGIA 2: Consultar sin currency
            all_mappings = self._query_basic(isin)
        
        if not all_mappings:
            # ESTRATEGIA 3: Intentar variantes de moneda según país
            country_code = isin[:2]
            currencies = self.country_currencies.get(country_code, [main_currency])
            
            for currency_variant in currencies:
                if currency_variant != main_currency:
                    all_mappings = self._query_with_currency(isin, currency_variant)
                    if all_mappings:
                        break
        
        # Procesar cada MIC solicitado
        for mic_data in mic_data_list:
            mic = mic_data['mic']
            currency = mic_data['currency']
            
            if all_mappings:
                # Buscar el mejor match
                best_match, match_type = self._find_best_match_advanced(mic, all_mappings)
                
                if best_match:
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': currency,
                        'ticker': best_match.get('ticker'),
                        'exchange_code': best_match.get('exchCode'),
                        'mic_code': best_match.get('micCode'),
                        'name': best_match.get('name'),
                        'security_type': best_match.get('securityType'),
                        'market_sector': best_match.get('marketSector'),
                        'match_type': match_type,
                        'source': 'OpenFIGI',
                        'warning': None if match_type == 'exact' else f'Using {match_type} match'
                    })
                else:
                    # Fallback al primer resultado
                    fallback = all_mappings[0]
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': currency,
                        'ticker': fallback.get('ticker'),
                        'exchange_code': fallback.get('exchCode'),
                        'mic_code': fallback.get('micCode'),
                        'name': fallback.get('name'),
                        'security_type': fallback.get('securityType'),
                        'market_sector': fallback.get('marketSector'),
                        'match_type': 'fallback',
                        'source': 'OpenFIGI',
                        'warning': f'MIC {mic} not found'
                    })
            else:
                # Sin resultados
                results.append({
                    'isin': isin,
                    'mic_requested': mic,
                    'currency_requested': currency,
                    'ticker': None,
                    'exchange_code': None,
                    'mic_code': None,
                    'name': None,
                    'security_type': None,
                    'market_sector': None,
                    'match_type': None,
                    'source': None,
                    'warning': 'No mapping found'
                })
        
        return results
    
    def _find_best_match_advanced(self, requested_mic: str, mappings: List[Dict]) -> tuple:
        """
        Encuentra el mejor match con lógica avanzada
        Retorna: (mapping_dict, match_type)
        """
        # 1. Match EXACTO por micCode
        for mapping in mappings:
            if mapping.get('micCode') == requested_mic:
                return mapping, 'exact'
        
        # 2. Match EXACTO por exchCode
        for mapping in mappings:
            if mapping.get('exchCode') == requested_mic:
                return mapping, 'exact'
        
        # 3. Match RELACIONADO (para MICs de US)
        if requested_mic in self.mic_relationships.get('US', []):
            for mapping in mappings:
                if mapping.get('exchCode') == 'US':
                    return mapping, 'related'
        
        # 4. Verificar relaciones inversas
        for parent_mic, related_mics in self.mic_relationships.items():
            if requested_mic in related_mics:
                for mapping in mappings:
                    if mapping.get('exchCode') == parent_mic:
                        return mapping, 'related'
        
        # 5. Match PARCIAL (contiene el MIC solicitado)
        for mapping in mappings:
            exch = mapping.get('exchCode', '')
            mic_code = mapping.get('micCode', '')
            if requested_mic in exch or requested_mic in mic_code:
                return mapping, 'partial'
        
        return None, None
    
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
print("TEST RESOLVER ULTRA AVANZADO")
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
            
            key = f"{isin}|{mic}"
            if key not in seen and isin and mic:
                seen.add(key)
                isin_mic_currency_data.append((isin, mic, currency))

print(f"\n📊 Total casos únicos: {len(isin_mic_currency_data)}")
print(f"📋 Procesando con estrategias avanzadas...\n")

# Resolver
resolver = UltraAdvancedISINResolver(rate_limit_delay=0.5)
results = resolver.resolve_batch(isin_mic_currency_data)

print("\n" + "="*80)
print("ANÁLISIS FINAL")
print("="*80)

# Estadísticas
total = len(results)
with_ticker = [r for r in results if r['ticker']]
without_ticker = [r for r in results if not r['ticker']]

exact_match = [r for r in results if r['match_type'] == 'exact']
related_match = [r for r in results if r['match_type'] == 'related']
partial_match = [r for r in results if r['match_type'] == 'partial']
fallback_match = [r for r in results if r['match_type'] == 'fallback']

print(f"\n📊 ESTADÍSTICAS GENERALES:")
print(f"   Total: {total}")
print(f"   ✅ Con ticker: {len(with_ticker)} ({len(with_ticker)/total*100:.1f}%)")
print(f"   ❌ Sin ticker: {len(without_ticker)} ({len(without_ticker)/total*100:.1f}%)")

print(f"\n📊 CALIDAD DE MATCHES:")
print(f"   🎯 Match EXACTO: {len(exact_match)} ({len(exact_match)/total*100:.1f}%)")
print(f"   🔗 Match RELACIONADO: {len(related_match)} ({len(related_match)/total*100:.1f}%)")
print(f"   📍 Match PARCIAL: {len(partial_match)} ({len(partial_match)/total*100:.1f}%)")
print(f"   ⚠️  Fallback: {len(fallback_match)} ({len(fallback_match)/total*100:.1f}%)")

print(f"\n" + "="*80)
print("CONCLUSIÓN COMPARATIVA")
print("="*80)

tasa_ticker = len(with_ticker)/total*100
tasa_exacto = len(exact_match)/total*100

print(f"""
📈 RESULTADOS:
   Tasa de ticker obtenido: {tasa_ticker:.1f}%
   Tasa de match EXACTO de MIC: {tasa_exacto:.1f}%

📊 COMPARACIÓN CON ESTRATEGIAS ANTERIORES:

   Estrategia SIMPLE:
   - Ticker: ~85%
   - Match exacto MIC: 0%
   
   Estrategia ULTRA AVANZADA:
   - Ticker: {tasa_ticker:.1f}%
   - Match exacto MIC: {tasa_exacto:.1f}%
   
   {'✅ MEJORA SIGNIFICATIVA en match de MIC' if tasa_exacto > 15 else '⚠️ MEJORA MODERADA en match de MIC' if tasa_exacto > 5 else '❌ Sin mejora significativa'}

💡 RECOMENDACIÓN:
   {'Usar estrategia ultra avanzada si el match exacto de MIC es crítico' if tasa_exacto > 20 else 'Usar estrategia simple es suficiente, la complejidad adicional no aporta valor suficiente'}
""")

# Mostrar ejemplos de matches exactos
if exact_match:
    print(f"🎯 EJEMPLOS DE MATCH EXACTO ({len(exact_match)}):")
    for r in exact_match[:10]:
        print(f"   {r['isin']:15} | MIC: {r['mic_requested']:8} → Ticker: {r['ticker']:10}")

# Mostrar fallos
if without_ticker:
    print(f"\n❌ CASOS SIN RESOLVER ({len(without_ticker)}):")
    for r in without_ticker[:15]:
        print(f"   {r['isin']:15} | {r['mic_requested']:8} ({r['currency_requested']}) | {r['warning']}")

print()

