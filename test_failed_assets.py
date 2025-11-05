#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para simular las peticiones exactas que hace el sistema
para los activos fallidos (HSBK, ZOMD)
"""

import requests
import json
import time

def test_asset(ticker_symbol):
    """
    Simula las mismas peticiones que hace PriceUpdater para un ticker específico
    """
    print("\n" + "="*100)
    print(f"🔍 TESTEANDO: {ticker_symbol}")
    print("="*100)
    
    # 1. AUTENTICACIÓN (obtener cookie y crumb)
    print("\n📍 PASO 1: AUTENTICACIÓN")
    print("-"*100)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
        'Connection': 'keep-alive',
    })
    
    try:
        # Obtener cookie
        print("   🔐 Obteniendo cookie...")
        response = session.get('https://finance.yahoo.com', timeout=10)
        print(f"   ✓ Status: {response.status_code}")
        print(f"   ✓ Cookies recibidas: {len(session.cookies)}")
        
        time.sleep(0.5)
        
        # Obtener crumb
        print("\n   🔑 Obteniendo crumb...")
        crumb_response = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10)
        print(f"   ✓ Status: {crumb_response.status_code}")
        crumb = crumb_response.text.strip()
        print(f"   ✓ Crumb: {crumb[:20]}...")
        
        auth_ok = True
    except Exception as e:
        print(f"   ❌ Error en autenticación: {e}")
        auth_ok = False
        return
    
    # 2. CHART API (obtener precio básico)
    print("\n📍 PASO 2: CHART API (Precio básico)")
    print("-"*100)
    
    chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
    print(f"   📋 URL: {chart_url}")
    print(f"   📋 Headers: {dict(session.headers)}")
    
    try:
        chart_response = session.get(chart_url, timeout=10)
        print(f"\n   ✅ Status Code: {chart_response.status_code}")
        print(f"   ✅ Content-Type: {chart_response.headers.get('Content-Type')}")
        print(f"   ✅ Content-Length: {len(chart_response.content)} bytes")
        
        if chart_response.status_code == 200:
            try:
                chart_data = chart_response.json()
                print(f"\n   📊 Estructura JSON recibida:")
                print(f"      - Keys principales: {list(chart_data.keys())}")
                
                if 'chart' in chart_data:
                    chart_obj = chart_data['chart']
                    print(f"      - chart.keys(): {list(chart_obj.keys())}")
                    
                    if 'error' in chart_obj and chart_obj['error']:
                        print(f"\n   ❌ ERROR en respuesta:")
                        print(f"      {json.dumps(chart_obj['error'], indent=6)}")
                    
                    if 'result' in chart_obj and chart_obj['result']:
                        result = chart_obj['result'][0]
                        print(f"      - result[0].keys(): {list(result.keys())}")
                        
                        if 'meta' in result:
                            meta = result['meta']
                            print(f"\n   💰 META DATA:")
                            print(f"      - Keys disponibles: {list(meta.keys())}")
                            print(f"      - currency: {meta.get('currency')}")
                            print(f"      - symbol: {meta.get('symbol')}")
                            print(f"      - exchangeName: {meta.get('exchangeName')}")
                            print(f"      - regularMarketPrice: {meta.get('regularMarketPrice')}")
                            print(f"      - previousClose: {meta.get('previousClose')}")
                            
                            if meta.get('regularMarketPrice'):
                                current = meta.get('regularMarketPrice')
                                previous = meta.get('previousClose')
                                if previous and previous > 0:
                                    change_pct = ((current - previous) / previous) * 100
                                    print(f"      - day_change_percent: {change_pct:.2f}%")
                            else:
                                print(f"\n   ⚠️ NO SE ENCONTRÓ 'regularMarketPrice' en meta")
                        else:
                            print(f"\n   ⚠️ NO SE ENCONTRÓ 'meta' en result")
                    else:
                        print(f"\n   ⚠️ NO SE ENCONTRÓ 'result' o está vacío")
                        print(f"      - chart.result: {chart_obj.get('result')}")
                
            except json.JSONDecodeError as e:
                print(f"   ❌ Error al parsear JSON: {e}")
                print(f"   📄 Contenido recibido (primeros 500 chars):")
                print(f"      {chart_response.text[:500]}")
        else:
            print(f"\n   ❌ Error HTTP: {chart_response.status_code}")
            print(f"   📄 Contenido recibido:")
            print(f"      {chart_response.text[:500]}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error en la petición: {e}")
    
    # 3. QUOTESUMMARY API (obtener datos avanzados)
    print("\n📍 PASO 3: QUOTESUMMARY API (Datos avanzados)")
    print("-"*100)
    
    quote_url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker_symbol}"
    params = {
        'modules': 'assetProfile,summaryDetail,defaultKeyStatistics,financialData',
        'crumb': crumb
    }
    print(f"   📋 URL: {quote_url}")
    print(f"   📋 Params: {params}")
    
    try:
        quote_response = session.get(quote_url, params=params, timeout=10)
        print(f"\n   ✅ Status Code: {quote_response.status_code}")
        print(f"   ✅ Content-Type: {quote_response.headers.get('Content-Type')}")
        print(f"   ✅ Content-Length: {len(quote_response.content)} bytes")
        
        if quote_response.status_code == 200:
            try:
                quote_data = quote_response.json()
                print(f"\n   📊 Estructura JSON recibida:")
                print(f"      - Keys principales: {list(quote_data.keys())}")
                
                if 'quoteSummary' in quote_data:
                    summary_obj = quote_data['quoteSummary']
                    print(f"      - quoteSummary.keys(): {list(summary_obj.keys())}")
                    
                    if 'error' in summary_obj and summary_obj['error']:
                        print(f"\n   ❌ ERROR en respuesta:")
                        print(f"      {json.dumps(summary_obj['error'], indent=6)}")
                    
                    if 'result' in summary_obj and summary_obj['result']:
                        result = summary_obj['result'][0]
                        print(f"      - result[0].keys(): {list(result.keys())}")
                        
                        # Asset Profile (Sector, Industry)
                        if 'assetProfile' in result:
                            profile = result['assetProfile']
                            print(f"\n   🏢 ASSET PROFILE:")
                            print(f"      - sector: {profile.get('sector')}")
                            print(f"      - industry: {profile.get('industry')}")
                        
                        # Summary Detail (Market Cap, Dividends)
                        if 'summaryDetail' in result:
                            summary = result['summaryDetail']
                            print(f"\n   💰 SUMMARY DETAIL:")
                            print(f"      - marketCap: {summary.get('marketCap')}")
                            print(f"      - trailingPE: {summary.get('trailingPE')}")
                            print(f"      - dividendRate: {summary.get('dividendRate')}")
                            print(f"      - dividendYield: {summary.get('dividendYield')}")
                        
                        # Default Key Statistics (Beta, Forward PE)
                        if 'defaultKeyStatistics' in result:
                            stats = result['defaultKeyStatistics']
                            print(f"\n   📊 KEY STATISTICS:")
                            print(f"      - beta: {stats.get('beta')}")
                            print(f"      - forwardPE: {stats.get('forwardPE')}")
                        
                        # Financial Data (Recommendations, Target Price)
                        if 'financialData' in result:
                            financial = result['financialData']
                            print(f"\n   🎯 FINANCIAL DATA:")
                            print(f"      - recommendationKey: {financial.get('recommendationKey')}")
                            print(f"      - numberOfAnalystOpinions: {financial.get('numberOfAnalystOpinions')}")
                            print(f"      - targetMeanPrice: {financial.get('targetMeanPrice')}")
                    else:
                        print(f"\n   ⚠️ NO SE ENCONTRÓ 'result' o está vacío")
                        print(f"      - quoteSummary.result: {summary_obj.get('result')}")
                        
            except json.JSONDecodeError as e:
                print(f"   ❌ Error al parsear JSON: {e}")
                print(f"   📄 Contenido recibido (primeros 500 chars):")
                print(f"      {quote_response.text[:500]}")
        else:
            print(f"\n   ❌ Error HTTP: {quote_response.status_code}")
            print(f"   📄 Contenido recibido:")
            print(f"      {quote_response.text[:500]}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error en la petición: {e}")


if __name__ == "__main__":
    print("╔" + "="*98 + "╗")
    print("║" + " "*20 + "TEST DE ACTIVOS FALLIDOS - SIMULACIÓN COMPLETA" + " "*31 + "║")
    print("╚" + "="*98 + "╝")
    
    # Tickers que fallaron en el último update
    failed_tickers = ["HSBK", "ZOMD"]
    
    for ticker in failed_tickers:
        test_asset(ticker)
        print("\n" + "⏳ Esperando 2 segundos antes del siguiente...\n")
        time.sleep(2)
    
    print("\n" + "="*100)
    print("✅ TEST COMPLETADO")
    print("="*100)

