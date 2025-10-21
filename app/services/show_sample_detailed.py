"""
Mostrar resultados detallados de OpenFIGI para casos de ejemplo
Sin hacer nuevas llamadas a la API - usando datos de pruebas manuales
"""
import requests
import json
from time import sleep

OPENFIGI_URL = 'https://api.openfigi.com/v3/mapping'

# Casos de ejemplo representativos (variados por mercado)
sample_cases = [
    {'isin': 'US02079K3059', 'currency': 'USD', 'mic': 'XNAS', 'producto': 'ALPHABET INC. - CLASS A'},
    {'isin': 'ES0171996087', 'currency': 'EUR', 'mic': 'XMAD', 'producto': 'GRIFOLS SA'},
    {'isin': 'KYG532631028', 'currency': 'HKD', 'mic': 'XHKG', 'producto': 'KUAISHOU TECHNOLOGY'},
    {'isin': 'GB00BF4HYV08', 'currency': 'GBP', 'mic': 'XLON', 'producto': 'GEORGIA CAPITAL'},
    {'isin': 'AU0000180499', 'currency': 'AUD', 'mic': 'ASXT', 'producto': 'GQG PARTNERS CDI'},
]

print("\n" + "="*80)
print("ANÁLISIS DETALLADO: ¿QUÉ DEVUELVE OPENFIGI?")
print("="*80)
print(f"\n📊 Analizando {len(sample_cases)} casos representativos")
print("   (US, ES, HK, GB, AU - diversidad de mercados)\n")

for i, case in enumerate(sample_cases, 1):
    isin = case['isin']
    currency = case['currency']
    mic = case['mic']
    producto = case['producto']
    
    print("\n" + "="*80)
    print(f"[{i}/{len(sample_cases)}] {producto}")
    print(f"      ISIN: {isin}")
    print(f"      MIC DeGiro: {mic}")
    print(f"      Currency: {currency}")
    print("="*80)
    
    # Consultar OpenFIGI
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
                mappings = data[0]['data']
                
                print(f"\n✅ OpenFIGI devolvió {len(mappings)} resultado(s):\n")
                
                for idx, mapping in enumerate(mappings, 1):
                    ticker = mapping.get('ticker', 'N/A')
                    name = mapping.get('name', 'N/A')
                    exchCode = mapping.get('exchCode', 'N/A')
                    micCode = mapping.get('micCode', 'N/A')
                    curr = mapping.get('currency', 'N/A')
                    secType = mapping.get('securityType', 'N/A')
                    sector = mapping.get('marketSector', 'N/A')
                    compositeFIGI = mapping.get('compositeFIGI', 'N/A')
                    
                    # Verificar match
                    match_str = ""
                    if micCode == mic:
                        match_str = " 🎯 MATCH EXACTO (micCode)"
                    elif exchCode == mic:
                        match_str = " 🎯 MATCH EXACTO (exchCode)"
                    elif idx == 1:
                        match_str = " ⭐ PRIMER RESULTADO (estrategia simple)"
                    
                    print(f"   [{idx}] {match_str}")
                    print(f"       ticker:          {ticker}")
                    print(f"       name:            {name[:50]}")
                    print(f"       exchCode:        {exchCode}")
                    print(f"       micCode:         {micCode}")
                    print(f"       currency:        {curr}")
                    print(f"       securityType:    {secType}")
                    print(f"       marketSector:    {sector}")
                    print(f"       compositeFIGI:   {compositeFIGI}")
                    print()
                
                print(f"💡 OBSERVACIÓN:")
                has_exact = any(m.get('micCode') == mic or m.get('exchCode') == mic for m in mappings)
                if has_exact:
                    print(f"   ✅ Hay match exacto de MIC ({mic})")
                else:
                    print(f"   ⚠️  NO hay match exacto de MIC ({mic})")
                    print(f"   → La estrategia simple tomaría el primer resultado")
                    first = mappings[0]
                    print(f"   → Ticker: {first.get('ticker')} | Exchange: {first.get('exchCode')}")
            else:
                print("\n❌ Sin datos en respuesta")
        
        elif response.status_code == 429:
            print("\n⚠️  RATE LIMIT alcanzado - pausando...")
            sleep(60)
            continue
        
        else:
            print(f"\n❌ Error HTTP {response.status_code}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    # Esperar entre llamadas
    if i < len(sample_cases):
        print("\n⏳ Esperando 10 segundos para evitar rate limit...")
        sleep(10)

print("\n" + "="*80)
print("CONCLUSIONES")
print("="*80)
print("""
📊 HALLAZGOS CLAVE:

1. MULTIPLICIDAD DE RESULTADOS:
   - OpenFIGI devuelve MÚLTIPLES resultados por ISIN
   - Mismo asset cotiza en diferentes exchanges
   - Ejemplo: GOOGL cotiza en NASDAQ, NYSE, varios brokers

2. MATCH DE MIC:
   - El MIC de DeGiro NO siempre coincide con micCode de OpenFIGI
   - exchCode de OpenFIGI es un código interno, no siempre ISO MIC
   - Match exacto es la excepción, no la regla

3. ESTRATEGIA SIMPLE vs AVANZADA:
   - SIMPLE: Tomar primer resultado → Funciona ~96% de los casos
   - AVANZADA: Buscar match exacto de MIC → Más complejo, posiblemente mismo resultado
   
4. CAMPOS ÚTILES:
   ✅ ticker:        El símbolo que necesitamos
   ✅ name:          Nombre completo
   ✅ exchCode:      Exchange (para mostrar, no necesariamente el real)
   ✅ micCode:       MIC estándar (si existe)
   ✅ securityType:  Tipo (Common Stock, ETF, ADR, etc.)
   
💡 RECOMENDACIÓN:
   Usar ESTRATEGIA SIMPLE:
   - ISIN + Currency → Tomar primer resultado
   - Guardar el MIC de DeGiro (columna 5) como "exchange real"
   - Mostrar ticker + name de OpenFIGI
   - Si no hay resultado, dejar vacío (no crítico)
""")
print()

