"""
Entry point para la aplicación FollowUp
"""
import os
from app import create_app

# Determinar el entorno
config_name = os.getenv('FLASK_ENV', 'development')

# Crear la aplicación
app = create_app(config_name)

if __name__ == '__main__':
    # Puerto configurable (producción usa 5000)
    port = int(os.environ.get('PORT', 5000))
    
    # En producción, Flask no debe correr con debug
    is_debug = config_name == 'development'
    
    print(f"🚀 FollowUp iniciando en modo: {config_name}")
    print(f"📍 Puerto: {port}")
    print(f"🔧 Debug: {is_debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=is_debug,
        threaded=True  # Permite múltiples peticiones simultáneas (necesario para barra de progreso)
    )

