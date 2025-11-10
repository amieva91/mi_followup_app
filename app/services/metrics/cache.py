"""
Servicio de cache para métricas del portfolio.

Este servicio gestiona el almacenamiento temporal de métricas calculadas
para evitar recálculos costosos en cada visita al dashboard.
"""
from datetime import datetime
from app import db
from app.models.metrics_cache import MetricsCache


class MetricsCacheService:
    """
    Servicio para gestionar el cache de métricas del portfolio.
    
    Usage:
        # Intentar obtener del cache
        metrics = MetricsCacheService.get(user_id)
        
        if metrics is None:
            # No existe o expiró, calcular
            metrics = BasicMetrics.get_all_metrics(...)
            
            # Guardar en cache
            MetricsCacheService.set(user_id, metrics)
        
        # Invalidar cuando algo cambia
        MetricsCacheService.invalidate(user_id)
    """
    
    @staticmethod
    def get(user_id):
        """
        Obtiene las métricas cacheadas para un usuario.
        
        Args:
            user_id (int): ID del usuario
            
        Returns:
            dict: Diccionario con las métricas cacheadas, o None si no existe o expiró
        """
        cache = MetricsCache.query.filter_by(user_id=user_id).first()
        
        # No existe cache
        if not cache:
            return None
        
        # Cache expirado (>24 horas)
        if not cache.is_valid:
            # Eliminar cache expirado
            db.session.delete(cache)
            db.session.commit()
            return None
        
        # Cache válido - añadir metadata
        cached_data = cache.cached_data.copy()
        cached_data['_cached_at'] = cache.created_at.isoformat()
        cached_data['_expires_at'] = cache.expires_at.isoformat()
        cached_data['_from_cache'] = True
        
        return cached_data
    
    @staticmethod
    def set(user_id, metrics_data):
        """
        Guarda las métricas calculadas en el cache.
        
        Args:
            user_id (int): ID del usuario
            metrics_data (dict): Diccionario con las métricas calculadas
            
        Returns:
            MetricsCache: Instancia del cache guardado
        """
        cache = MetricsCache.query.filter_by(user_id=user_id).first()
        
        # Limpiar metadata interna si existe
        clean_data = {k: v for k, v in metrics_data.items() if not k.startswith('_')}
        
        if cache:
            # Actualizar cache existente
            cache.cached_data = clean_data
            cache.created_at = datetime.utcnow()
            cache.expires_at = MetricsCache.get_default_expiry()
        else:
            # Crear nuevo cache
            cache = MetricsCache(
                user_id=user_id,
                cached_data=clean_data,
                created_at=datetime.utcnow(),
                expires_at=MetricsCache.get_default_expiry()
            )
            db.session.add(cache)
        
        db.session.commit()
        return cache
    
    @staticmethod
    def invalidate(user_id):
        """
        Invalida (elimina) el cache de métricas para un usuario.
        
        Esto debe llamarse cuando:
        - Se crea/edita/elimina una transacción
        - Se actualizan precios de assets
        - Se actualiza la conversión de divisas
        - El usuario solicita un recálculo manual
        
        Args:
            user_id (int): ID del usuario
            
        Returns:
            bool: True si se eliminó cache, False si no existía
        """
        cache = MetricsCache.query.filter_by(user_id=user_id).first()
        
        if cache:
            db.session.delete(cache)
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def invalidate_all():
        """
        Invalida el cache de TODOS los usuarios.
        
        Útil cuando:
        - Se actualiza la lógica de cálculo de métricas
        - Se corrige un bug en los cálculos
        - Se despliega una nueva versión con cambios en métricas
        
        Returns:
            int: Número de caches eliminados
        """
        count = MetricsCache.query.delete()
        db.session.commit()
        return count
    
    @staticmethod
    def get_stats():
        """
        Obtiene estadísticas del cache.
        
        Returns:
            dict: Estadísticas del cache (total, válidos, expirados)
        """
        total = MetricsCache.query.count()
        valid = MetricsCache.query.filter(
            MetricsCache.expires_at > datetime.utcnow()
        ).count()
        expired = total - valid
        
        return {
            'total': total,
            'valid': valid,
            'expired': expired
        }

