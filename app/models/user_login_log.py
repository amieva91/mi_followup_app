"""
Registro de inicios de sesión para el panel de administración.
"""
from datetime import datetime
from app import db


class UserLoginLog(db.Model):
    """Registro de cada login (user_id, fecha, IP opcional)."""
    __tablename__ = 'user_login_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    logged_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 max length

    user = db.relationship('User', backref=db.backref('login_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<UserLoginLog user_id={self.user_id} at {self.logged_at}>'
