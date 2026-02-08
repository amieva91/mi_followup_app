"""
Modelo de Usuario para autenticación
"""
from datetime import datetime
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from app import db, bcrypt


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
    
    # Configuración financiera
    debt_limit_percent = db.Column(db.Float, default=35.0, nullable=True)
    
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

