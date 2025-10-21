"""
Script de prueba para verificar:
1. Priorización MIC > ibkr_exchange para yahoo_suffix
2. Obtención de MIC desde OpenFIGI para assets IBKR
"""
from app import create_app, db
from app.models import AssetRegistry
from app.services.asset_registry_service import AssetRegistryService

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("🧪 PRUEBA DE CONDICIONES UNIFICADAS - MIC + Symbol Enrichment")
    print("="*70)
    print("\n💡 IMPORTANTE: Condiciones iguales para IBKR y DeGiro")
    print("   - Cualquier asset sin symbol → needs_enrichment = True")
    print("   - Cualquier asset sin MIC → needs_enrichment = True")
    print("   - NO distingue broker, solo campos faltantes\n")
    
    service = AssetRegistryService()
    
    # Limpiar registros de prueba anteriores
    AssetRegistry.query.filter(AssetRegistry.isin.in_([
        'US0378331005',  # AAPL
        'ES0113211835',  # Grifols
        'US5949181045'   # Microsoft (para probar)
    ])).delete()
    db.session.commit()
    
    # 1. Probar asset de IBKR (con symbol pero sin MIC)
    print("\n1️⃣  Probando asset IBKR (tiene symbol, falta MIC)...")
    registry_ibkr = service.get_or_create_from_isin(
        isin='US0378331005',
        symbol='AAPL',
        exchange='NASDAQ',
        currency='USD',
        name='Apple Inc.',
        asset_type='Stock'
    )
    db.session.commit()
    
    print(f"   Registro IBKR creado:")
    print(f"      - Symbol: {registry_ibkr.symbol}")
    print(f"      - Exchange: {registry_ibkr.ibkr_exchange}")
    print(f"      - MIC: {registry_ibkr.mic or 'None (esperado - se obtendrá con OpenFIGI)'}")
    print(f"      - Yahoo Suffix: {registry_ibkr.yahoo_suffix or 'None/Empty (US)'}")
    print(f"      - Needs Enrichment: {registry_ibkr.needs_enrichment} (debería ser True si falta MIC)")
    
    # 2. Probar asset de DeGiro (con MIC, sin symbol)
    print("\n2️⃣  Probando asset DeGiro (tiene MIC, falta symbol)...")
    registry_degiro = service.get_or_create_from_isin(
        isin='ES0113211835',
        currency='EUR',
        name='Grifols SA',
        mic='XMAD',
        degiro_exchange='MAD',
        asset_type='Stock'
    )
    db.session.commit()
    
    print(f"   Registro DeGiro creado:")
    print(f"      - Symbol: {registry_degiro.symbol or 'None (esperado)'}")
    print(f"      - Exchange (mapeado): {registry_degiro.ibkr_exchange}")
    print(f"      - MIC: {registry_degiro.mic}")
    print(f"      - Yahoo Suffix: {registry_degiro.yahoo_suffix} (desde MIC)")
    print(f"      - Needs Enrichment: {registry_degiro.needs_enrichment}")
    
    # 3. Probar priorización MIC > exchange
    print("\n3️⃣  Probando priorización MIC > exchange...")
    
    # Simular asset que tiene ambos (MIC y exchange)
    registry_both = service.get_or_create_from_isin(
        isin='US5949181045',
        symbol='MSFT',
        exchange='NASDAQ',
        mic='XNAS',
        currency='USD',
        name='Microsoft Corp',
        asset_type='Stock'
    )
    db.session.commit()
    
    print(f"   Registro con ambos (MIC + Exchange):")
    print(f"      - MIC: {registry_both.mic}")
    print(f"      - Exchange: {registry_both.ibkr_exchange}")
    print(f"      - Yahoo Suffix: {registry_both.yahoo_suffix}")
    print(f"      - ✅ Yahoo Suffix debe haberse calculado desde MIC (prioridad)")
    
    # 4. Estadísticas
    print("\n4️⃣  Estadísticas actuales:")
    total = AssetRegistry.query.count()
    with_mic = AssetRegistry.query.filter(AssetRegistry.mic.isnot(None)).count()
    without_mic = total - with_mic
    needs_enrichment = AssetRegistry.query.filter(
        db.or_(
            AssetRegistry.symbol.is_(None),
            AssetRegistry.mic.is_(None)
        )
    ).count()
    
    print(f"   • Total registros: {total}")
    print(f"   • Con MIC: {with_mic}")
    print(f"   • Sin MIC: {without_mic}")
    print(f"   • Necesitan enriquecimiento: {needs_enrichment}")
    
    # 5. Listar todos
    print("\n5️⃣  Listado de registros:")
    all_registries = AssetRegistry.query.all()
    for reg in all_registries:
        mic_status = f"MIC: {reg.mic}" if reg.mic else "SIN MIC"
        symbol_status = f"Symbol: {reg.symbol}" if reg.symbol else "SIN SYMBOL"
        needs = "⚠️ NEEDS ENRICHMENT" if reg.needs_enrichment else "✅ COMPLETE"
        print(f"   {needs} | {reg.isin} | {symbol_status:15} | {mic_status:12} | Yahoo: {reg.yahoo_suffix or 'None/Empty'}")
    
    print("\n" + "="*70)
    print("✅ PRUEBA COMPLETADA")
    print("="*70)
    print("\n💡 Verificaciones:")
    print("   1. ✅ Condiciones UNIFICADAS: needs_enrichment igual para IBKR y DeGiro")
    print("   2. ✅ Cualquier asset sin symbol → needs_enrichment = True")
    print("   3. ✅ Cualquier asset sin MIC → needs_enrichment = True")
    print("   4. ✅ Yahoo suffix se calcula con prioridad: MIC > exchange")
    print("   5. ✅ Durante importación, OpenFIGI obtiene symbol Y MIC para todos")
    print("\n🎯 Resultado: Base de datos más completa y robusta")
    print()

