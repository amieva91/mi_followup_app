#!/usr/bin/env python3
"""
Test completo de autenticación con Yahoo Finance
1. Obtener cookie
2. Obtener crumb
3. Usar cookie + crumb en quoteSummary
"""

import requests
import time

def get_yahoo_data_with_auth(symbol):
    """
    Flujo completo de autenticación y obtención de datos
    """
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    print(f"\n{'─' * 80}")
    print(f"🔐 PASO 1: Obtener cookie de Yahoo Finance")
    print(f"{'─' * 80}")
    
    try:
        # Visitar página principal de Yahoo Finance para obtener cookie
        response = session.get('https://finance.yahoo.com', timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Cookies recibidas: {len(session.cookies)}")
        
        if len(session.cookies) > 0:
            print(f"   ✅ Cookie obtenido")
            for cookie in session.cookies:
                print(f"      - {cookie.name}")
        else:
            print(f"   ⚠️ No se obtuvieron cookies")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None, f"Error al obtener cookie: {e}"
    
    time.sleep(1)
    
    print(f"\n{'─' * 80}")
    print(f"🔑 PASO 2: Obtener crumb")
    print(f"{'─' * 80}")
    
    try:
        # Obtener crumb usando el cookie
        crumb_url = "https://query1.finance.yahoo.com/v1/test/getcrumb"
        crumb_response = session.get(crumb_url, timeout=10)
        
        print(f"   Status: {crumb_response.status_code}")
        print(f"   Respuesta: {crumb_response.text[:100]}")
        
        if crumb_response.status_code == 200:
            crumb = crumb_response.text.strip()
            if crumb and crumb != "null" and "Too Many Requests" not in crumb:
                print(f"   ✅ Crumb obtenido: {crumb[:20]}...")
            else:
                print(f"   ❌ Crumb inválido: {crumb}")
                return None, f"Crumb inválido: {crumb}"
        else:
            print(f"   ❌ Error HTTP {crumb_response.status_code}")
            return None, f"Error al obtener crumb: {crumb_response.status_code}"
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None, f"Error al obtener crumb: {e}"
    
    time.sleep(1)
    
    print(f"\n{'─' * 80}")
    print(f"📊 PASO 3: Consultar quoteSummary con cookie + crumb")
    print(f"{'─' * 80}")
    
    try:
        # Usar cookie + crumb para obtener datos
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
        params = {
            'modules': 'price,assetProfile,summaryDetail',
            'crumb': crumb
        }
        
        print(f"   URL: {url}")
        print(f"   Crumb: {crumb[:20]}...")
        
        response = session.get(url, params=params, timeout=10)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'quoteSummary' not in data:
                return None, "No quoteSummary en respuesta"
            
            if data['quoteSummary'].get('error'):
                error = data['quoteSummary']['error']
                return None, f"Error API: {error}"
            
            result_data = data['quoteSummary']['result']
            if not result_data:
                return None, "Sin resultados"
            
            # Extraer datos
            info = result_data[0]
            
            output = {
                'symbol': symbol,
            }
            
            # PRECIO
            if 'price' in info:
                price_data = info['price']
                output['current_price'] = price_data.get('regularMarketPrice', {}).get('raw')
                output['currency'] = price_data.get('currency')
            
            # SECTOR e INDUSTRY
            if 'assetProfile' in info:
                profile = info['assetProfile']
                output['sector'] = profile.get('sector')
                output['industry'] = profile.get('industry')
            
            print(f"   ✅ Datos obtenidos correctamente")
            
            return output, None
            
        elif response.status_code == 401:
            print(f"   ❌ 401 Unauthorized")
            print(f"   Respuesta: {response.text[:200]}")
            return None, "401 Unauthorized - crumb inválido"
        elif response.status_code == 429:
            return None, "429 Rate limit"
        else:
            print(f"   ❌ HTTP {response.status_code}")
            print(f"   Respuesta: {response.text[:200]}")
            return None, f"HTTP {response.status_code}"
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None, f"Exception: {str(e)}"

print("=" * 80)
print("🧪 TEST: Flujo completo de autenticación Yahoo Finance")
print("=" * 80)

# Probar con un símbolo simple
symbol = "AAPL"

print(f"\n🎯 Probando con: {symbol}")

data, error = get_yahoo_data_with_auth(symbol)

print(f"\n{'=' * 80}")
print("📋 RESULTADO FINAL:")
print(f"{'=' * 80}")

if data:
    print(f"✅ ÉXITO - Datos obtenidos:")
    print(f"   Symbol:    {data.get('symbol')}")
    print(f"   Precio:    {data.get('current_price')} {data.get('currency')}")
    print(f"   Sector:    {data.get('sector')}")
    print(f"   Industry:  {data.get('industry')}")
    print(f"\n🎉 ¡Funciona! Podemos integrar esto en el sistema")
else:
    print(f"❌ FALLÓ: {error}")
    print(f"\n💡 Posibles causas:")
    print(f"   1. IP bloqueada temporalmente por Yahoo Finance")
    print(f"   2. Necesitamos más headers o configuración")
    print(f"   3. Yahoo cambió su sistema de autenticación")
    print(f"   4. Necesitamos usar proxy o esperar 24-48 horas")

print("=" * 80)

