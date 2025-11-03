#!/usr/bin/env python3
"""
Mostrar todos los datos guardados en la base de datos para cada activo
"""

from app import create_app, db
from app.models.asset import Asset

app = create_app()

with app.app_context():
    # Obtener todos los activos
    assets = Asset.query.order_by(Asset.symbol).all()
    
    print("=" * 100)
    print("📊 DATOS ALMACENADOS EN LA BASE DE DATOS PARA CADA ACTIVO")
    print("=" * 100)
    
    # Campos a verificar
    campos_precio = [
        'current_price',
        'previous_close',
        'day_change_percent',
        'last_price_update'
    ]
    
    campos_valoracion = [
        'market_cap',
        'market_cap_formatted',
        'market_cap_eur',
        'trailing_pe',
        'forward_pe'
    ]
    
    campos_corporativo = [
        'sector',
        'industry'
    ]
    
    campos_riesgo = [
        'beta',
        'dividend_rate',
        'dividend_yield'
    ]
    
    campos_analisis = [
        'recommendation_key',
        'number_of_analyst_opinions',
        'target_mean_price'
    ]
    
    for asset in assets:
        print(f"\n{'─' * 100}")
        print(f"🔹 {asset.symbol or asset.name} ({asset.currency})")
        print(f"   ISIN: {asset.isin}")
        print(f"   Yahoo Ticker: {asset.yahoo_ticker}")
        print(f"{'─' * 100}")
        
        # PRECIOS
        print("\n   💰 PRECIOS Y CAMBIOS:")
        for campo in campos_precio:
            valor = getattr(asset, campo, None)
            icono = "✅" if valor is not None else "❌"
            print(f"      {icono} {campo:25} = {valor}")
        
        # VALORACIÓN
        print("\n   📈 VALORACIÓN:")
        for campo in campos_valoracion:
            valor = getattr(asset, campo, None)
            icono = "✅" if valor is not None else "❌"
            print(f"      {icono} {campo:25} = {valor}")
        
        # CORPORATIVO
        print("\n   🏢 INFORMACIÓN CORPORATIVA:")
        for campo in campos_corporativo:
            valor = getattr(asset, campo, None)
            icono = "✅" if valor is not None else "❌"
            print(f"      {icono} {campo:25} = {valor}")
        
        # RIESGO
        print("\n   ⚠️ RIESGO Y RENDIMIENTO:")
        for campo in campos_riesgo:
            valor = getattr(asset, campo, None)
            icono = "✅" if valor is not None else "❌"
            print(f"      {icono} {campo:25} = {valor}")
        
        # ANÁLISIS
        print("\n   🎯 ANÁLISIS DE MERCADO:")
        for campo in campos_analisis:
            valor = getattr(asset, campo, None)
            icono = "✅" if valor is not None else "❌"
            print(f"      {icono} {campo:25} = {valor}")
    
    print(f"\n{'=' * 100}")
    print("📊 RESUMEN:")
    print(f"   Total de activos analizados: {len(assets)}")
    print("=" * 100)
    
    # Contar campos vacíos
    total_campos = len(campos_precio + campos_valoracion + campos_corporativo + campos_riesgo + campos_analisis)
    campos_con_datos = 0
    campos_sin_datos = 0
    
    for asset in assets:
        for campo in (campos_precio + campos_valoracion + campos_corporativo + campos_riesgo + campos_analisis):
            if getattr(asset, campo, None) is not None:
                campos_con_datos += 1
            else:
                campos_sin_datos += 1
    
    print(f"\n   ✅ Campos con datos:    {campos_con_datos}/{total_campos * len(assets)}")
    print(f"   ❌ Campos sin datos:    {campos_sin_datos}/{total_campos * len(assets)}")
    print(f"   📊 % Completitud:       {(campos_con_datos / (total_campos * len(assets)) * 100):.1f}%")
    print("\n" + "=" * 100)

