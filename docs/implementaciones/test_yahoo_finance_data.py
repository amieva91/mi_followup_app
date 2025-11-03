#!/usr/bin/env python3
"""
Script para explorar qué datos podemos obtener de Yahoo Finance
"""
import yfinance as yf
from datetime import datetime

# Ejemplos de assets que tienes en tu portfolio
test_symbols = [
    "ASTS",      # AST SpaceMobile (US)
    "GRF.MC",    # Grifols (España)
    "AVXL",      # Anavex (NASDAQ)
    "ACCD",      # Accolade
    "0700.HK"    # Tencent (Hong Kong)
]

def explore_yahoo_data(symbol):
    """Explorar todos los datos disponibles para un símbolo"""
    print(f"\n{'='*80}")
    print(f"📊 EXPLORANDO: {symbol}")
    print(f"{'='*80}\n")
    
    try:
        ticker = yf.Ticker(symbol)
        
        # 1. INFO BÁSICA (ticker.info)
        info = ticker.info
        
        print("📌 INFORMACIÓN DISPONIBLE:\n")
        
        # Precio actual
        print(f"💰 PRECIOS:")
        print(f"   - Precio actual: {info.get('currentPrice', 'N/A')}")
        print(f"   - Precio anterior cierre: {info.get('previousClose', 'N/A')}")
        print(f"   - Precio apertura: {info.get('open', 'N/A')}")
        print(f"   - Precio máximo día: {info.get('dayHigh', 'N/A')}")
        print(f"   - Precio mínimo día: {info.get('dayLow', 'N/A')}")
        print(f"   - Máximo 52 semanas: {info.get('fiftyTwoWeekHigh', 'N/A')}")
        print(f"   - Mínimo 52 semanas: {info.get('fiftyTwoWeekLow', 'N/A')}")
        
        # Información de la empresa
        print(f"\n🏢 EMPRESA:")
        print(f"   - Nombre: {info.get('longName', 'N/A')}")
        print(f"   - Nombre corto: {info.get('shortName', 'N/A')}")
        print(f"   - Sector: {info.get('sector', 'N/A')}")
        print(f"   - Industria: {info.get('industry', 'N/A')}")
        print(f"   - País: {info.get('country', 'N/A')}")
        print(f"   - Ciudad: {info.get('city', 'N/A')}")
        print(f"   - Exchange: {info.get('exchange', 'N/A')}")
        
        # Valoración y métricas
        print(f"\n📊 MÉTRICAS DE VALORACIÓN:")
        print(f"   - Market Cap: {info.get('marketCap', 'N/A')}")
        print(f"   - P/E Ratio: {info.get('trailingPE', 'N/A')}")
        print(f"   - Forward P/E: {info.get('forwardPE', 'N/A')}")
        print(f"   - PEG Ratio: {info.get('pegRatio', 'N/A')}")
        print(f"   - Price/Book: {info.get('priceToBook', 'N/A')}")
        print(f"   - Enterprise Value: {info.get('enterpriseValue', 'N/A')}")
        
        # Dividendos
        print(f"\n💵 DIVIDENDOS:")
        print(f"   - Dividend Rate: {info.get('dividendRate', 'N/A')}")
        print(f"   - Dividend Yield: {info.get('dividendYield', 'N/A')}")
        print(f"   - Ex-Dividend Date: {info.get('exDividendDate', 'N/A')}")
        print(f"   - Payout Ratio: {info.get('payoutRatio', 'N/A')}")
        
        # Riesgo y rendimiento
        print(f"\n⚠️ RIESGO:")
        print(f"   - Beta: {info.get('beta', 'N/A')}")
        print(f"   - 52 Week Change: {info.get('52WeekChange', 'N/A')}")
        
        # Volumen y liquidez
        print(f"\n📈 VOLUMEN:")
        print(f"   - Volumen: {info.get('volume', 'N/A')}")
        print(f"   - Volumen promedio: {info.get('averageVolume', 'N/A')}")
        print(f"   - Average Volume 10 days: {info.get('averageVolume10days', 'N/A')}")
        
        # Moneda
        print(f"\n💱 MONEDA:")
        print(f"   - Currency: {info.get('currency', 'N/A')}")
        print(f"   - Financial Currency: {info.get('financialCurrency', 'N/A')}")
        
        # Recomendaciones de analistas
        print(f"\n👔 ANALISTAS:")
        print(f"   - Recomendación: {info.get('recommendationKey', 'N/A')}")
        print(f"   - Target High Price: {info.get('targetHighPrice', 'N/A')}")
        print(f"   - Target Low Price: {info.get('targetLowPrice', 'N/A')}")
        print(f"   - Target Mean Price: {info.get('targetMeanPrice', 'N/A')}")
        print(f"   - Número de analistas: {info.get('numberOfAnalystOpinions', 'N/A')}")
        
        # 2. HISTÓRICO (últimos 5 días)
        print(f"\n📅 HISTÓRICO (últimos 5 días):")
        history = ticker.history(period="5d")
        if not history.empty:
            print(history[['Open', 'High', 'Low', 'Close', 'Volume']])
        else:
            print("   No hay datos históricos disponibles")
        
        # 3. CALENDARIO (próximos eventos)
        print(f"\n📆 CALENDARIO:")
        calendar = ticker.calendar
        if calendar is not None and not calendar.empty:
            print(calendar)
        else:
            print("   No hay eventos en el calendario")
        
        # 4. RECOMENDACIONES
        print(f"\n💡 RECOMENDACIONES DE ANALISTAS:")
        recommendations = ticker.recommendations
        if recommendations is not None and not recommendations.empty:
            print(recommendations.tail(5))
        else:
            print("   No hay recomendaciones disponibles")
        
        print(f"\n✅ Exploración completada para {symbol}\n")
        
    except Exception as e:
        print(f"❌ Error al obtener datos para {symbol}: {e}\n")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔍 EXPLORACIÓN DE DATOS DISPONIBLES EN YAHOO FINANCE")
    print("="*80)
    
    for symbol in test_symbols:
        explore_yahoo_data(symbol)
        
    print("\n" + "="*80)
    print("📋 RESUMEN DE DATOS ÚTILES PARA TU APLICACIÓN:")
    print("="*80)
    print("""
    ✅ ESENCIALES (Alta prioridad):
       - currentPrice: Precio actual para calcular valor de mercado
       - previousClose: Para calcular cambio diario
       - currency: Moneda del precio
       - marketCap: Capitalización de mercado
       
    ✅ MUY ÚTILES (Media prioridad):
       - sector, industry, country: Para clasificación y filtros
       - beta: Para análisis de riesgo
       - dividendRate, dividendYield: Para proyección de dividendos
       - fiftyTwoWeekHigh, fiftyTwoWeekLow: Para contexto
       
    ✅ INTERESANTES (Baja prioridad - futuro):
       - trailingPE, forwardPE: Ratios de valoración
       - targetMeanPrice: Precio objetivo según analistas
       - recommendationKey: Recomendación de analistas
       - averageVolume: Liquidez del asset
    """)
    print("="*80)

