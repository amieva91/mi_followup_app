"""
Script para recalcular yahoo_suffix en AssetRegistry
Útil después de ediciones manuales que no recalculan el suffix
"""
from app import create_app, db
from app.models import AssetRegistry
from app.services.asset_registry_service import AssetRegistryService

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("🔧 RECALCULANDO YAHOO_SUFFIX PARA TODOS LOS ASSETS")
    print("="*70 + "\n")
    
    service = AssetRegistryService()
    
    # Obtener todos los registros
    all_registries = AssetRegistry.query.all()
    
    updated = 0
    skipped = 0
    
    for registry in all_registries:
        old_suffix = registry.yahoo_suffix
        
        # Recalcular usando el método del servicio
        service._set_yahoo_suffix(registry, registry.mic, registry.ibkr_exchange)
        
        if old_suffix != registry.yahoo_suffix:
            print(f"✅ Actualizado: {registry.isin} ({registry.symbol or 'sin symbol'})")
            print(f"   Suffix: '{old_suffix}' → '{registry.yahoo_suffix}'")
            updated += 1
        else:
            skipped += 1
    
    # Guardar cambios
    db.session.commit()
    
    print("\n" + "="*70)
    print("✅ RECALCULACIÓN COMPLETADA")
    print("="*70)
    print(f"\n📊 Resumen:")
    print(f"   • Assets actualizados: {updated}")
    print(f"   • Assets sin cambios: {skipped}")
    print(f"   • Total procesados: {len(all_registries)}")
    
    # Mostrar Grifols específicamente
    print(f"\n🔍 Verificación Grifols:")
    grifols = AssetRegistry.query.filter_by(isin='ES0113211835').first()
    if grifols:
        print(f"   • Symbol: {grifols.symbol}")
        print(f"   • MIC: {grifols.mic}")
        print(f"   • Exchange: {grifols.ibkr_exchange}")
        print(f"   • Yahoo Suffix: {grifols.yahoo_suffix}")
        print(f"   • Yahoo Ticker: {grifols.yahoo_ticker}")
    
    print()

