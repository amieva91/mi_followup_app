"""
Script para limpiar el cache de métricas
"""
import sys
sys.path.insert(0, '/home/ssoo/www')

from app import create_app, db
from app.models import User
from app.services.metrics.cache import MetricsCacheService

app = create_app()

with app.app_context():
    user = User.query.first()
    if not user:
        print("No hay usuarios")
        sys.exit(1)
    
    user_id = user.id
    
    print(f"Limpiando cache para usuario {user_id}...")
    was_invalidated = MetricsCacheService.invalidate(user_id)
    
    if was_invalidated:
        print("✅ Cache invalidado correctamente")
    else:
        print("ℹ️ No había cache para invalidar")
    
    print("\nEl dashboard recalculará las métricas en la próxima carga.")

