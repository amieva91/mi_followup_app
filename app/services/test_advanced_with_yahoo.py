"""
Test del resolver avanzado con fallback a Yahoo Finance
Usando los 191 casos únicos del CSV de DeGiro
"""
import requests
import json
import pandas as pd
import csv
from time import sleep
from typing import Optional, Dict, List

class AdvancedISINResolver:
    """
    Resuelve ISIN + MIC específico a Ticker + Exchange
    Con fallback a Yahoo Finance para casos que OpenFIGI no resuelve
    """
    
    def __init__(self, rate_limit_delay=0.1, use_yahoo_fallback=False, verbose=False):
        self.rate_limit_delay = rate_limit_delay
        self.use_yahoo_fallback = use_yahoo_fallback
        self.verbose = verbose
        self.openfigi_url = 'https://api.openfigi.com/v3/mapping'
        self.cache = {}
        
        # MICs consolidados vs específicos
        self.mic_relationships = {
            'US': ['XNYS', 'XNAS', 'ARCX', 'BATS', 'CDED', 'SOHO', 'MEMX', 
                   'MSPL', 'EDGX', 'EPRL', 'XBOS', 'IEXG'],
        }
    
    def resolve_batch(self, df_input: pd.DataFrame) -> pd.DataFrame:
        """
        Resuelve un DataFrame con columnas: ISIN, MIC, Currency, Producto
        Retorna DataFrame con ticker y exchange_code
        """
        results = []
        
        # Obtener combinaciones únicas ISIN + MIC
        unique_pairs = df_input[['ISIN', 'MIC', 'Currency', 'Producto']].drop_duplicates()
        
        # Agrupar por ISIN para optimizar
        isin_groups = {}
        for _, row in unique_pairs.iterrows():
            isin = row['ISIN']
            mic = row['MIC']
            currency = row['Currency']
            producto = row['Producto']
            if isin not in isin_groups:
                isin_groups[isin] = []
            isin_groups[isin].append({'mic': mic, 'currency': currency, 'producto': producto})
        
        total = len(isin_groups)
        for idx, (isin, mics_data) in enumerate(isin_groups.items(), 1):
            producto_ref = mics_data[0]['producto']
            print(f"[{idx:3d}/{total}] {isin:15} | {producto_ref[:30]:30}", end='')
            
            # Resolver para todos los MICs de este ISIN
            isin_results = self._resolve_isin_all_mics(isin, mics_data)
            results.extend(isin_results)
            
            resolved = sum(1 for r in isin_results if r['ticker'] is not None)
            sources = set(r.get('source', 'Unknown') for r in isin_results if r['ticker'] is not None)
            source_str = ','.join(sources) if sources else ''
            print(f" | {resolved}/{len(mics_data)} [{source_str}]")
            
            # Mostrar detalle de cada MIC si está activado verbose
            if self.verbose:
                for result in isin_results:
                    status = "✅" if result['ticker'] else "❌"
                    ticker = result['ticker'] or "N/A"
                    exchange = result['exchange_code'] or "N/A"
                    mic = result['mic_code'] or "N/A"
                    match = result.get('match_type', 'N/A')
                    src = result.get('source', 'N/A')
                    print(f"      {status} MIC:{result['mic_requested']:8s} → Ticker:{ticker:10s} Exchange:{exchange:8s} Match:{match:10s} Source:{src}")
            
            sleep(self.rate_limit_delay)
        
        return pd.DataFrame(results)
    
    def _resolve_isin_all_mics(self, isin: str, mics_data: List[Dict]) -> List[Dict]:
        """Resuelve un ISIN para múltiples MICs específicos"""
        results = []
        
        # 1. Intentar con OpenFIGI primero
        all_mappings = self._get_all_mappings(isin, mics_data[0]['currency'])
        
        if all_mappings:
            # OpenFIGI tiene datos
            for mic_data in mics_data:
                mic = mic_data['mic']
                best_match = self._find_best_match(mic, all_mappings)
                
                if best_match:
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': mic_data['currency'],
                        'producto': mic_data['producto'],
                        'ticker': best_match.get('ticker'),
                        'exchange_code': best_match.get('exchCode'),
                        'mic_code': best_match.get('micCode'),
                        'name': best_match.get('name'),
                        'figi': best_match.get('figi'),
                        'currency': best_match.get('currency'),
                        'security_type': best_match.get('securityType'),
                        'market_sector': best_match.get('marketSector'),
                        'composite_figi': best_match.get('compositeFIGI'),
                        'match_type': 'exact' if best_match.get('micCode') == mic else 'fallback',
                        'source': 'OpenFIGI'
                    })
                else:
                    # Usar primer resultado como fallback
                    fallback = all_mappings[0]
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': mic_data['currency'],
                        'producto': mic_data['producto'],
                        'ticker': fallback.get('ticker'),
                        'exchange_code': fallback.get('exchCode'),
                        'mic_code': fallback.get('micCode'),
                        'name': fallback.get('name'),
                        'figi': fallback.get('figi'),
                        'currency': fallback.get('currency'),
                        'security_type': fallback.get('securityType'),
                        'market_sector': fallback.get('marketSector'),
                        'composite_figi': fallback.get('compositeFIGI'),
                        'match_type': 'fallback',
                        'source': 'OpenFIGI',
                        'warning': f'MIC {mic} not found, using {fallback.get("exchCode")}'
                    })
        else:
            # Sin resultados de OpenFIGI
            for mic_data in mics_data:
                results.append(self._create_empty_result(
                    isin, mic_data['mic'], mic_data['currency'], mic_data['producto'],
                    "No mapping found in OpenFIGI"
                ))
        
        return results
    
    def _get_all_mappings(self, isin: str, currency: str) -> List[Dict]:
        """Obtiene TODOS los mappings posibles para un ISIN"""
        # Consulta con currency específica
        query = {'idType': 'ID_ISIN', 'idValue': isin, 'currency': currency}
        results = self._query_openfigi(query)
        
        if not results:
            # Fallback: consulta sin currency
            query = {'idType': 'ID_ISIN', 'idValue': isin}
            results = self._query_openfigi(query)
        
        return results
    
    def _find_best_match(self, requested_mic: str, mappings: List[Dict]) -> Optional[Dict]:
        """Encuentra el mejor match para un MIC específico"""
        # 1. Match exacto por micCode
        for mapping in mappings:
            if mapping.get('micCode') == requested_mic:
                return mapping
        
        # 2. Match por exchCode
        for mapping in mappings:
            if mapping.get('exchCode') == requested_mic:
                return mapping
        
        # 3. Si el MIC solicitado es específico de US, buscar cualquier US
        if requested_mic in self.mic_relationships.get('US', []):
            for mapping in mappings:
                if mapping.get('exchCode') == 'US':
                    return mapping
        
        # 4. Verificar si el MIC del mapping está relacionado
        for parent_mic, related_mics in self.mic_relationships.items():
            if requested_mic in related_mics:
                for mapping in mappings:
                    if mapping.get('exchCode') == parent_mic:
                        return mapping
        
        return None
    
    def _query_openfigi(self, query: Dict) -> List[Dict]:
        """Consulta OpenFIGI API con una query específica"""
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
                    elif 'error' in data[0]:
                        return []
            elif response.status_code == 429:
                print(" [RATE_LIMIT]", end='')
                sleep(60)
                return self._query_openfigi(query)
                
        except Exception as e:
            print(f" [ERR:{str(e)[:20]}]", end='')
        
        return []
    
    def _create_empty_result(self, isin: str, mic: str, currency: str, producto: str, warning: str) -> Dict:
        """Crea un resultado vacío con warning"""
        return {
            'isin': isin,
            'mic_requested': mic,
            'currency_requested': currency,
            'producto': producto,
            'ticker': None,
            'exchange_code': None,
            'mic_code': None,
            'name': None,
            'figi': None,
            'currency': None,
            'security_type': None,
            'market_sector': None,
            'composite_figi': None,
            'match_type': None,
            'source': None,
            'warning': warning
        }


# Script principal
print("\n" + "="*80)
print("TEST RESOLVER AVANZADO CON 191 CASOS DE DEGIRO")
print("="*80)

# Leer CSV de DeGiro
csv_path = "uploads/TransaccionesDegiro.csv"
data = []
seen = set()

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        if len(row) > 8:
            isin = row[3].strip()
            mic = row[5].strip()
            currency = row[8].strip() or 'EUR'
            producto = row[2].strip()
            
            key = f"{isin}|{mic}"
            if key not in seen and isin and mic:
                seen.add(key)
                data.append({
                    'ISIN': isin,
                    'MIC': mic,
                    'Currency': currency,
                    'Producto': producto
                })

df_input = pd.DataFrame(data)

print(f"\n📊 Total casos únicos (ISIN + MIC): {len(df_input)}")
print(f"🔧 Yahoo Finance fallback: DESACTIVADO (por ahora)")
print(f"🔍 Modo verbose: ✅ ACTIVADO (mostrando detalle de cada MIC)")
print(f"⏱️  Tiempo estimado: {len(df_input) * 0.1 / 60:.1f} minutos\n")

# Resolver
resolver = AdvancedISINResolver(
    rate_limit_delay=0.1,
    use_yahoo_fallback=False,
    verbose=True  # ✅ ACTIVADO para ver detalle de cada MIC
)
results_df = resolver.resolve_batch(df_input)

# Análisis
print("\n" + "="*80)
print("ANÁLISIS DE RESULTADOS")
print("="*80)

total = len(results_df)
with_ticker = results_df['ticker'].notna().sum()
exact_match = (results_df['match_type'] == 'exact').sum()
fallback_match = (results_df['match_type'] == 'fallback').sum()

print(f"\n📊 ESTADÍSTICAS:")
print(f"   Total casos: {total}")
print(f"   ✅ Con ticker: {with_ticker} ({with_ticker/total*100:.1f}%)")
print(f"   ❌ Sin ticker: {total - with_ticker} ({(total-with_ticker)/total*100:.1f}%)")
print(f"\n   🎯 Match EXACTO de MIC: {exact_match} ({exact_match/total*100:.1f}%)")
print(f"   ⚠️  Match FALLBACK: {fallback_match} ({fallback_match/total*100:.1f}%)")

# Casos sin resolver
unresolved = results_df[results_df['ticker'].isna()]
if not unresolved.empty:
    print(f"\n❌ CASOS SIN RESOLVER ({len(unresolved)}):")
    for _, row in unresolved.head(20).iterrows():
        print(f"   {row['isin']:15} | {row['mic_requested']:8} ({row['currency_requested']}) | {row['producto'][:40]}")
    
    if len(unresolved) > 20:
        print(f"   ... y {len(unresolved) - 20} más")

# Guardar resultados
results_df.to_csv('advanced_resolver_results.csv', index=False)
print(f"\n💾 Resultados guardados en 'advanced_resolver_results.csv'")

# Guardar solo fallos
unresolved.to_csv('advanced_resolver_failures.csv', index=False)
print(f"💾 {len(unresolved)} fallos guardados en 'advanced_resolver_failures.csv'")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)

tasa_exito = with_ticker/total*100
tasa_match_exacto = exact_match/total*100

print(f"""
📈 RESULTADOS FINALES:
   Tasa de éxito (ticker obtenido): {tasa_exito:.1f}%
   Tasa de match EXACTO de MIC:     {tasa_match_exacto:.1f}%
   
💡 OBSERVACIONES:
   - Si el match exacto de MIC es bajo (<20%), no aporta valor significativo
   - La estrategia simple (tomar primer resultado) sería igual de efectiva
   - El MIC de DeGiro (columna 5) debe guardarse por separado de todos modos
   
✅ RECOMENDACIÓN:
   {'Usar estrategia SIMPLE si el match exacto < 20%' if tasa_match_exacto < 20 else 'La estrategia avanzada aporta valor si el match exacto es significativo'}
""")
print()

