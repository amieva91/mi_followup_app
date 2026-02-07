"""
Watchlist Service - Gestión de watchlist (CRUD básico)
"""
from typing import List, Optional, Dict, Any
from app import db
from app.models import Watchlist, WatchlistConfig, Asset, User
from datetime import datetime


class WatchlistService:
    """
    Servicio para gestión de watchlist (CRUD básico)
    """
    
    @staticmethod
    def get_user_watchlist(user_id: int) -> List[Watchlist]:
        """
        Obtiene todos los assets en watchlist del usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Lista de Watchlist items ordenados por created_at (más recientes primero)
        """
        return Watchlist.query.filter_by(user_id=user_id).order_by(Watchlist.created_at.desc()).all()
    
    @staticmethod
    def get_watchlist_item(user_id: int, asset_id: int) -> Optional[Watchlist]:
        """
        Obtiene un item específico de watchlist
        
        Args:
            user_id: ID del usuario
            asset_id: ID del asset
            
        Returns:
            Watchlist item o None si no existe
        """
        return Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()
    
    @staticmethod
    def add_to_watchlist(user_id: int, asset_id: int, datos_manuales: Optional[Dict[str, Any]] = None) -> Watchlist:
        """
        Añade un asset a la watchlist del usuario
        
        Args:
            user_id: ID del usuario
            asset_id: ID del asset
            datos_manuales: Dict opcional con campos manuales iniciales
                Ejemplo: {'next_earnings_date': date, 'per_ntm': 15.0, ...}
        
        Returns:
            Watchlist item creado
            
        Raises:
            ValueError: Si el asset ya está en watchlist
        """
        # Verificar que no existe ya
        existing = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()
        if existing:
            raise ValueError(f"El asset ya está en la watchlist del usuario")
        
        # Verificar que el asset existe
        asset = Asset.query.get(asset_id)
        if not asset:
            raise ValueError(f"Asset con ID {asset_id} no existe")
        
        # Verificar que el usuario existe
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"Usuario con ID {user_id} no existe")
        
        # Crear nuevo item de watchlist
        watchlist_item = Watchlist(
            user_id=user_id,
            asset_id=asset_id,
            operativa_indicator='-'  # Valor por defecto
        )
        
        # Aplicar datos manuales si se proporcionan
        if datos_manuales:
            if 'next_earnings_date' in datos_manuales:
                watchlist_item.next_earnings_date = datos_manuales['next_earnings_date']
            if 'per_ntm' in datos_manuales:
                watchlist_item.per_ntm = datos_manuales['per_ntm']
            if 'ntm_dividend_yield' in datos_manuales:
                watchlist_item.ntm_dividend_yield = datos_manuales['ntm_dividend_yield']
            if 'eps' in datos_manuales:
                watchlist_item.eps = datos_manuales['eps']
            if 'cagr_revenue_yoy' in datos_manuales:
                watchlist_item.cagr_revenue_yoy = datos_manuales['cagr_revenue_yoy']
        
        db.session.add(watchlist_item)
        db.session.commit()
        
        return watchlist_item
    
    @staticmethod
    def remove_from_watchlist(user_id: int, asset_id: int) -> bool:
        """
        Elimina un asset de la watchlist del usuario.
        También borra en cascada: informes de compañía (company_reports)
        y resumen About (asset_about_summary) para ese usuario y asset.
        
        Args:
            user_id: ID del usuario
            asset_id: ID del asset
            
        Returns:
            True si se eliminó, False si no existía
        """
        watchlist_item = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()
        if not watchlist_item:
            return False

        # Borrado en cascada: informes y resumen About
        from app.models.company_report import CompanyReport, AssetAboutSummary
        CompanyReport.query.filter_by(user_id=user_id, asset_id=asset_id).delete()
        AssetAboutSummary.query.filter_by(user_id=user_id, asset_id=asset_id).delete()

        db.session.delete(watchlist_item)
        db.session.commit()
        return True
    
    @staticmethod
    def update_watchlist_asset(watchlist_id: int, datos: Dict[str, Any], commit: bool = False) -> Optional[Watchlist]:
        """
        Actualiza un item de watchlist con nuevos datos manuales
        
        Args:
            watchlist_id: ID del item de watchlist
            datos: Dict con campos a actualizar (solo campos manuales)
                Ejemplo: {'next_earnings_date': date, 'per_ntm': 15.0, ...}
            commit: Si True, hace commit. Si False, solo actualiza sin commit (para que se pueda recalcular después)
        
        Returns:
            Watchlist item actualizado o None si no existe
        """
        watchlist_item = Watchlist.query.get(watchlist_id)
        if not watchlist_item:
            return None
        
        # Actualizar solo campos manuales permitidos
        campos_permitidos = ['next_earnings_date', 'per_ntm', 'ntm_dividend_yield', 'eps', 'cagr_revenue_yoy']
        
        for campo, valor in datos.items():
            if campo in campos_permitidos and hasattr(watchlist_item, campo):
                setattr(watchlist_item, campo, valor)
        
        watchlist_item.updated_at = datetime.utcnow()
        
        if commit:
            db.session.commit()
        
        return watchlist_item
    
    @staticmethod
    def get_or_create_config(user_id: int) -> WatchlistConfig:
        """
        Obtiene o crea la configuración de watchlist para un usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            WatchlistConfig (creado con valores por defecto si no existe)
        """
        config = WatchlistConfig.query.filter_by(user_id=user_id).first()
        
        if not config:
            config = WatchlistConfig(
                user_id=user_id,
                max_weight_threshold=10.0  # Valor por defecto 10%
            )
            # Establecer valores por defecto para Tier
            config.set_tier_ranges_dict(config._default_tier_ranges())
            config.set_tier_amounts_dict(config._default_tier_amounts())
            
            db.session.add(config)
            db.session.commit()
        
        return config
    
    @staticmethod
    def update_config(user_id: int, max_weight_threshold: Optional[float] = None,
                     tier_ranges: Optional[Dict] = None, tier_amounts: Optional[Dict] = None,
                     color_thresholds: Optional[Dict] = None) -> WatchlistConfig:
        """
        Actualiza la configuración de watchlist del usuario
        
        Args:
            user_id: ID del usuario
            max_weight_threshold: Nuevo umbral máximo peso en cartera (opcional)
            tier_ranges: Nuevos rangos de Tier (opcional)
            tier_amounts: Nuevas cantidades por Tier (opcional)
            color_thresholds: Nuevos umbrales de colores (opcional)
        
        Returns:
            WatchlistConfig actualizado
        """
        config = WatchlistService.get_or_create_config(user_id)
        
        if max_weight_threshold is not None:
            config.max_weight_threshold = max_weight_threshold
        
        if tier_ranges is not None:
            config.set_tier_ranges_dict(tier_ranges)
        
        if tier_amounts is not None:
            config.set_tier_amounts_dict(tier_amounts)
        
        if color_thresholds is not None:
            config.set_color_thresholds_dict(color_thresholds)
        
        config.updated_at = datetime.utcnow()
        db.session.commit()
        
        return config

