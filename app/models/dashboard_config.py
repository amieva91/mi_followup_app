"""
Modelo para configuración personalizada del Dashboard
"""
from datetime import datetime
from app import db


# Widgets disponibles con configuración por defecto
DEFAULT_WIDGETS = [
    {'id': 'net_worth', 'name': 'Patrimonio Total', 'icon': '💰', 'enabled': True, 'position': 1},
    {'id': 'evolution_chart', 'name': 'Evolución Patrimonio', 'icon': '📈', 'enabled': True, 'position': 2},
    {'id': 'projection', 'name': 'Previsión 1/3/5 años', 'icon': '🔮', 'enabled': True, 'position': 3},
    {'id': 'cash', 'name': 'Cash & Bancos', 'icon': '🏦', 'enabled': True, 'position': 4},
    {'id': 'portfolio', 'name': 'Portfolio', 'icon': '📊', 'enabled': True, 'position': 5},
    {'id': 'crypto', 'name': 'Crypto', 'icon': '₿', 'enabled': True, 'position': 6},
    {'id': 'metales', 'name': 'Metales', 'icon': '🥇', 'enabled': True, 'position': 7},
    {'id': 'debt', 'name': 'Deudas', 'icon': '📋', 'enabled': True, 'position': 8},
    {'id': 'income_expense', 'name': 'Ingresos/Gastos Mes', 'icon': '💵', 'enabled': True, 'position': 9},
    {'id': 'savings_rate', 'name': 'Tasa de Ahorro', 'icon': '📉', 'enabled': True, 'position': 10},
    {'id': 'top_expenses', 'name': 'Top Gastos Mes', 'icon': '🔥', 'enabled': True, 'position': 11},
    {'id': 'upcoming_payments', 'name': 'Próximos Pagos', 'icon': '📅', 'enabled': True, 'position': 12},
    {'id': 'investments_summary', 'name': 'Rentabilidad Inversiones', 'icon': '📈', 'enabled': True, 'position': 13},
    {'id': 'recent_transactions', 'name': 'Últimos Movimientos', 'icon': '🔄', 'enabled': True, 'position': 14},
    {'id': 'currency_exposure', 'name': 'Exposición Divisas', 'icon': '💱', 'enabled': True, 'position': 15},
    {'id': 'year_comparison', 'name': 'Comparativa Anual', 'icon': '📊', 'enabled': True, 'position': 16},
    {'id': 'health_score', 'name': 'Salud Financiera', 'icon': '❤️', 'enabled': True, 'position': 17},
]


class UserDashboardConfig(db.Model):
    """Configuración de widgets del dashboard por usuario."""
    __tablename__ = 'user_dashboard_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    widget_id = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'widget_id', name='uq_user_widget'),
    )
    
    user = db.relationship('User', backref=db.backref('dashboard_configs', lazy='dynamic'))
    
    @classmethod
    def get_user_config(cls, user_id: int) -> dict:
        """
        Obtiene la configuración del dashboard para un usuario.
        Si no existe, devuelve la configuración por defecto.
        """
        configs = cls.query.filter_by(user_id=user_id).all()
        
        if not configs:
            return {w['id']: w for w in DEFAULT_WIDGETS}
        
        # Combinar configuración guardada con defaults
        result = {}
        saved_ids = {c.widget_id for c in configs}
        
        for config in configs:
            widget_default = next((w for w in DEFAULT_WIDGETS if w['id'] == config.widget_id), None)
            if widget_default:
                result[config.widget_id] = {
                    'id': config.widget_id,
                    'name': widget_default['name'],
                    'icon': widget_default['icon'],
                    'enabled': config.enabled,
                    'position': config.position
                }
        
        # Añadir widgets por defecto que no estén guardados
        for w in DEFAULT_WIDGETS:
            if w['id'] not in saved_ids:
                result[w['id']] = w.copy()
        
        return result
    
    @classmethod
    def save_user_config(cls, user_id: int, widget_configs: list):
        """
        Guarda la configuración de widgets para un usuario.
        widget_configs: lista de dicts con {id, enabled, position}
        """
        for wc in widget_configs:
            existing = cls.query.filter_by(
                user_id=user_id, 
                widget_id=wc['id']
            ).first()
            
            if existing:
                existing.enabled = wc.get('enabled', True)
                existing.position = wc.get('position', 0)
            else:
                new_config = cls(
                    user_id=user_id,
                    widget_id=wc['id'],
                    enabled=wc.get('enabled', True),
                    position=wc.get('position', 0)
                )
                db.session.add(new_config)
        
        db.session.commit()
    
    @classmethod
    def get_enabled_widgets(cls, user_id: int) -> list:
        """Devuelve lista de widgets habilitados ordenados por posición."""
        config = cls.get_user_config(user_id)
        enabled = [w for w in config.values() if w['enabled']]
        return sorted(enabled, key=lambda x: x['position'])
