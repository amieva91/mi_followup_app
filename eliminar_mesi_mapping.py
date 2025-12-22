"""
Script para eliminar el mapeo MESI de la base de datos
Esto permite que assets con mic='MESI' usen el exchange como fallback
Ejecutar: python eliminar_mesi_mapping.py
"""
from app import create_app, db
from app.models import MappingRegistry

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("🗑️  ELIMINANDO MAPEO MESI DE LA BASE DE DATOS")
    print("="*70 + "\n")
    
    # Buscar mapeo MESI
    mesi_mapping = MappingRegistry.query.filter_by(
        mapping_type='MIC_TO_YAHOO',
        source_key='MESI'
    ).first()
    
    if mesi_mapping:
        print(f"✅ Mapeo encontrado:")
        print(f"   • MESI → {mesi_mapping.target_value}")
        print(f"   • País: {mesi_mapping.country or 'N/A'}")
        print(f"   • Descripción: {mesi_mapping.description or 'N/A'}")
        print(f"   • Creado por: {mesi_mapping.created_by}")
        print(f"   • Creado en: {mesi_mapping.created_at}")
        
        respuesta = input("\n⚠️  ¿Eliminar este mapeo? (s/n): ").strip().lower()
        
        if respuesta == 's':
            db.session.delete(mesi_mapping)
            db.session.commit()
            print("\n✅ Mapeo MESI eliminado exitosamente")
            print("\n📝 NOTA: Ahora los assets con mic='MESI' usarán el exchange como fallback")
            print("   Ejemplo: Volex (mic='MESI', exchange='EO') usará EO → .L")
        else:
            print("\n❌ Operación cancelada")
    else:
        print("ℹ️  No se encontró mapeo MESI en la base de datos")
        print("   Esto significa que ya está configurado para usar exchange como fallback")
    
    print("\n" + "="*70)
    print("✅ PROCESO COMPLETADO")
    print("="*70 + "\n")

