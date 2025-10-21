"""
Test del resolver avanzado con datos reales de DeGiro
"""
import csv
import requests
import json
from time import sleep
from typing import Optional, Dict, List

class ISINToTickerResolver:
    """
    Resuelve ISIN + MIC Code a Ticker + Exchange automáticamente
    usando múltiples fuentes sin hardcodear nada
    """
    
    def __init__(self, rate_limit_delay=0.5):
        self.rate_limit_delay = rate_limit_delay
        self.openfigi_url = 'https://api.openfigi.com/v3/mapping'
        self.cache = {}
        
        # Mapeo de monedas problemáticas a su base
        self.currency_variants = {
            'GBX': ['GBX', 'GBP', 'GBp'],  # Peniques UK
            'ZAC': ['ZAC', 'ZAR'],          # Centavos Sudáfrica
            'ILA': ['ILA', 'ILS'],          # Agorot Israel
        }
    
    def resolve_batch(self, isin_mic_list: List[tuple]) -> List[Dict]:
        """
        Resuelve un batch de (ISIN, MIC, Currency) 
        isin_mic_list: [(isin1, mic1, currency1), (isin2, mic2, currency2), ...]
        """
        results = []
        
        # Agrupar por ISIN para optimizar llamadas
        isin_groups = {}
        for isin, mic, currency in isin_mic_list:
            if isin not in isin_groups:
                isin_groups[isin] = []
            isin_groups[isin].append({'mic': mic, 'currency': currency})
        
        total = len(isin_groups)
        for idx, (isin, mic_data_list) in enumerate(isin_groups.items(), 1):
            print(f"[{idx:2d}/{total}] {isin:15} ", end='', flush=True)
            
            # Intentar resolver para todos los MICs de este ISIN
            isin_results = self._resolve_isin_all_mics(isin, mic_data_list)
            results.extend(isin_results)
            
            # Mostrar resultado resumido
            success = [r for r in isin_results if r['ticker']]
            print(f"| {len(success)}/{len(isin_results)} resueltos")
            
            sleep(self.rate_limit_delay)
        
        return results
    
    def _resolve_isin_all_mics(self, isin: str, mic_data_list: List[Dict]) -> List[Dict]:
        """Resuelve un ISIN para múltiples MICs"""
        results = []
        
        # Obtener currency del primer elemento (normalmente todos tienen la misma)
        main_currency = mic_data_list[0]['currency']
        
        # 1. Consultar OpenFIGI CON currency (más preciso)
        all_mappings = self._query_openfigi_with_currency(isin, main_currency)
        
        if not all_mappings:
            # 2. Intentar sin currency
            all_mappings = self._query_openfigi(isin, exchange_code=None)
        
        if not all_mappings:
            # 3. Intentar variantes de moneda
            all_mappings = self._try_currency_variants(isin, main_currency)
        
        # 4. Filtrar resultados por cada MIC solicitado
        for mic_data in mic_data_list:
            mic = mic_data['mic']
            currency = mic_data['currency']
            matched = False
            
            # Buscar coincidencia con el MIC en exchCode o micCode
            for mapping in all_mappings:
                exch_code = mapping.get('exchCode', '')
                mic_code = mapping.get('micCode', '')
                
                # Match directo
                if exch_code == mic or mic_code == mic:
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': currency,
                        'ticker': mapping.get('ticker'),
                        'exchange_code': mapping.get('exchCode'),
                        'mic_code': mapping.get('micCode'),
                        'name': mapping.get('name'),
                        'security_type': mapping.get('securityType'),
                        'source': 'OpenFIGI (exact match)',
                        'warning': None
                    })
                    matched = True
                    break
            
            if not matched:
                # Si no hay match exacto, usar el mejor disponible
                if all_mappings:
                    best = all_mappings[0]
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': currency,
                        'ticker': best.get('ticker'),
                        'exchange_code': best.get('exchCode'),
                        'mic_code': best.get('micCode'),
                        'name': best.get('name'),
                        'security_type': best.get('securityType'),
                        'source': 'OpenFIGI (best match)',
                        'warning': f'MIC {mic} not found, using {best.get("exchCode")}'
                    })
                else:
                    # No se encontró nada
                    results.append({
                        'isin': isin,
                        'mic_requested': mic,
                        'currency_requested': currency,
                        'ticker': None,
                        'exchange_code': None,
                        'mic_code': None,
                        'name': None,
                        'security_type': None,
                        'source': None,
                        'warning': 'No mapping found'
                    })
        
        return results
    
    def _query_openfigi_with_currency(self, isin: str, currency: str) -> List[Dict]:
        """Consulta OpenFIGI con ISIN + Currency"""
        query = {
            'idType': 'ID_ISIN',
            'idValue': isin,
            'currency': currency
        }
        
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
        except Exception as e:
            pass
        
        return []
    
    def _query_openfigi(self, isin: str, exchange_code: Optional[str] = None) -> List[Dict]:
        """Consulta OpenFIGI API"""
        query = {
            'idType': 'ID_ISIN',
            'idValue': isin
        }
        
        if exchange_code:
            query['exchCode'] = exchange_code
        
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
        except Exception as e:
            pass
        
        return []
    
    def _try_currency_variants(self, isin: str, base_currency: str) -> List[Dict]:
        """Intenta variantes de moneda para ISINs problemáticos"""
        # Si es GBX, intentar con GBP
        if base_currency == 'GBX':
            return self._query_openfigi_with_currency(isin, 'GBP')
        
        return []


# Script principal
print("\n" + "="*80)
print("TEST RESOLVER AVANZADO CON DATOS DE DEGIRO")
print("="*80)

# Leer CSV y extraer datos únicos
csv_path = "uploads/TransaccionesDegiro.csv"
isin_mic_data = []
seen = set()

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        if len(row) > 8:
            isin = row[3].strip()
            bolsa_de = row[4].strip()
            mic = row[5].strip()
            currency = row[8].strip() or 'EUR'
            
            # Crear clave única
            key = f"{isin}|{mic}"
            
            if key not in seen and isin and mic:
                seen.add(key)
                isin_mic_data.append((isin, mic, currency))

print(f"\n📊 Total casos únicos (ISIN + MIC): {len(isin_mic_data)}")
print(f"📋 Procesando...\n")

# Resolver
resolver = ISINToTickerResolver(rate_limit_delay=0.5)
results = resolver.resolve_batch(isin_mic_data)

print("\n" + "="*80)
print("ANÁLISIS DE RESULTADOS")
print("="*80)

# Estadísticas
total = len(results)
with_ticker = [r for r in results if r['ticker']]
without_ticker = [r for r in results if not r['ticker']]
exact_match = [r for r in results if r['source'] == 'OpenFIGI (exact match)']
best_match = [r for r in results if r['source'] == 'OpenFIGI (best match)']

print(f"\n📊 ESTADÍSTICAS:")
print(f"   Total casos: {total}")
print(f"   ✅ Con ticker: {len(with_ticker)} ({len(with_ticker)/total*100:.1f}%)")
print(f"   ❌ Sin ticker: {len(without_ticker)} ({len(without_ticker)/total*100:.1f}%)")
print(f"\n   📍 Match exacto MIC: {len(exact_match)} ({len(exact_match)/total*100:.1f}%)")
print(f"   📍 Best match (MIC diferente): {len(best_match)} ({len(best_match)/total*100:.1f}%)")

# Análisis por moneda
print(f"\n📈 FALLOS POR MONEDA:")
fallos_por_moneda = {}
for r in without_ticker:
    currency = r['currency_requested']
    if currency not in fallos_por_moneda:
        fallos_por_moneda[currency] = []
    fallos_por_moneda[currency].append(r)

for currency in sorted(fallos_por_moneda.keys()):
    casos = fallos_por_moneda[currency]
    print(f"   {currency}: {len(casos)} fallo(s)")

# Mostrar fallos
if without_ticker:
    print(f"\n❌ CASOS SIN RESOLVER ({len(without_ticker)}):")
    for r in without_ticker[:20]:  # Primeros 20
        print(f"   {r['isin']:15} | {r['mic_requested']:8} ({r['currency_requested']}) | {r['warning']}")

# Mostrar best matches (MIC diferente)
if best_match:
    print(f"\n⚠️  CASOS CON MIC DIFERENTE (primeros 10):")
    for r in best_match[:10]:
        print(f"   {r['isin']:15} | Solicitado: {r['mic_requested']:8} → Obtenido: {r['exchange_code']:8} | Ticker: {r['ticker']}")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)

tasa_exito = len(with_ticker)/total*100
tasa_exacto = len(exact_match)/total*100

print(f"""
📈 TASA DE ÉXITO (ticker obtenido): {tasa_exito:.1f}%
📈 TASA DE MATCH EXACTO (MIC correcto): {tasa_exacto:.1f}%

{'✅ EXCELENTE' if tasa_exito >= 85 else '✅ BUENA' if tasa_exito >= 75 else '⚠️ ACEPTABLE' if tasa_exito >= 60 else '❌ INSUFICIENTE'}

💡 COMPARACIÓN CON ESTRATEGIA SIMPLE:
   Estrategia Simple: ~85% ticker, 0% match exacto MIC
   Estrategia Avanzada: {tasa_exito:.1f}% ticker, {tasa_exacto:.1f}% match exacto MIC
   
   {'✅ MEJORA en match de MIC' if tasa_exacto > 10 else '⚠️  No mejora significativa en match de MIC'}
""")

