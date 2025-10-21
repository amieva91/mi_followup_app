"""
Script para actualizar precios de assets con holdings activos
"""
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.services.market_data import PriceUpdater

print("\n" + "="*70)
print("ACTUALIZACIÓN DE PRECIOS")
print("="*70)

# Crear contexto de aplicación
app = create_app()

with app.app_context():
    # Crear updater
    updater = PriceUpdater()
    
    # Actualizar todos los assets con holdings > 0
    stats = updater.update_prices_for_active_holdings()
    
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    print(f"""
✅ Precios actualizados: {stats['updated']}
⊘  Omitidos (sin ticker): {stats['skipped']}
❌ Fallidos:              {stats['failed']}

Total procesados: {stats['updated'] + stats['skipped'] + stats['failed']}
""")
    
    if stats['errors']:
        print("\n" + "-"*70)
        print("ERRORES:")
        for error in stats['errors']:
            print(f"  • {error}")
    
    print()

