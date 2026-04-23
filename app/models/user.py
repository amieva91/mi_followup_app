"""
Modelo de Usuario para autenticación
"""
from datetime import datetime
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from app import db, bcrypt


# Módulos disponibles (clave -> etiqueta). Si el módulo no existe, no se muestra en navbar.
MODULES = {
    'finance': 'Ingresos / Gastos / Deudas / Bancos',
    'stock': 'Acciones',
    'crypto': 'Criptomonedas',
    'metales': 'Metales',
    'real_estate': 'Real Estate',
    'pensions': 'Plan de pensiones',
}

# Avatares predefinidos (avatar_id -> path relativo a static)
AVATARS = {
    1: 'avatars/1.svg', 2: 'avatars/2.svg', 3: 'avatars/3.svg',
    4: 'avatars/4.svg', 5: 'avatars/5.svg', 6: 'avatars/6.svg',
    7: 'avatars/7.svg', 8: 'avatars/8.svg', 9: 'avatars/9.svg',
    10: 'avatars/10.svg', 11: 'avatars/11.svg', 12: 'avatars/12.svg',
    13: 'avatars/13.svg', 14: 'avatars/14.svg', 15: 'avatars/15.svg',
    16: 'avatars/16.svg', 17: 'avatars/17.svg', 18: 'avatars/18.svg',
    19: 'avatars/19.svg', 20: 'avatars/20.svg', 21: 'avatars/21.svg',
    22: 'avatars/22.svg', 23: 'avatars/23.svg', 24: 'avatars/24.svg',
    25: 'avatars/25.svg', 26: 'avatars/26.svg', 27: 'avatars/27.svg',
    28: 'avatars/28.svg', 29: 'avatars/29.svg', 30: 'avatars/30.svg',
    31: 'avatars/31.svg', 32: 'avatars/32.svg', 33: 'avatars/33.svg',
    34: 'avatars/34.svg', 35: 'avatars/35.svg', 36: 'avatars/36.svg',
    37: 'avatars/37.svg', 38: 'avatars/38.svg', 39: 'avatars/39.svg',
    40: 'avatars/40.svg', 41: 'avatars/41.svg', 42: 'avatars/42.svg',
    43: 'avatars/43.svg', 44: 'avatars/44.svg', 45: 'avatars/45.svg',
    46: 'avatars/46.svg', 47: 'avatars/47.svg', 48: 'avatars/48.svg',
    49: 'avatars/49.svg', 50: 'avatars/50.svg', 51: 'avatars/51.svg',
    52: 'avatars/52.svg', 53: 'avatars/53.svg', 54: 'avatars/54.svg',
    55: 'avatars/55.svg', 56: 'avatars/56.svg', 57: 'avatars/57.svg',
    58: 'avatars/58.svg', 59: 'avatars/59.svg', 60: 'avatars/60.svg',
    61: 'avatars/61.svg', 62: 'avatars/62.svg', 63: 'avatars/63.svg',
    64: 'avatars/64.svg', 65: 'avatars/65.svg', 66: 'avatars/66.svg',
    67: 'avatars/67.svg', 68: 'avatars/68.svg', 69: 'avatars/69.svg',
    70: 'avatars/70.svg', 71: 'avatars/71.svg', 72: 'avatars/72.svg',
    73: 'avatars/73.svg', 74: 'avatars/74.svg', 75: 'avatars/75.svg',
    76: 'avatars/76.svg', 77: 'avatars/77.svg', 78: 'avatars/78.svg',
    79: 'avatars/79.svg',
}


class User(UserMixin, db.Model):
    """Modelo de Usuario"""
    
    __tablename__ = 'users'
    
    # Campos principales
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Permisos y estado
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)  # True = primer inicio, obliga a cambiar
    
    # Configuración financiera
    debt_limit_percent = db.Column(db.Float, default=35.0, nullable=True)

    # Perfil
    avatar_id = db.Column(db.Integer, nullable=True)  # null = usar iniciales
    birth_year = db.Column(db.Integer, nullable=True)
    enabled_modules = db.Column(db.JSON, nullable=True)  # lista de claves: ['finance','stock',...]
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Hashear y guardar password"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Verificar password"""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Actualizar fecha de último login"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_reset_token(self, expires_sec=1800):
        """
        Generar token para reset de password (válido 30 minutos)
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')
    
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        """
        Verificar token de reset de password
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(
                token, 
                salt='password-reset-salt',
                max_age=expires_sec
            )['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    def get_avatar_url(self):
        """URL del avatar: imagen predefinida o None para usar iniciales"""
        if self.avatar_id and self.avatar_id in AVATARS:
            from flask import url_for
            return url_for('static', filename=AVATARS[self.avatar_id])
        return None

    def get_initials(self):
        """Iniciales del usuario (ej: Juan Sánchez -> JS)"""
        parts = self.username.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return (self.username[:2] if len(self.username) >= 2 else self.username).upper()

    def has_module(self, key):
        """Indica si el usuario tiene activado el módulo"""
        if self.enabled_modules is None:
            return True  # Por defecto todos activos
        return key in self.enabled_modules

    def get_enabled_modules(self):
        """Lista de módulos activados. Si None, todos activos."""
        if self.enabled_modules is None:
            return list(MODULES.keys())
        return self.enabled_modules

    def to_dict(self):
        """Convertir a diccionario (sin password)"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

