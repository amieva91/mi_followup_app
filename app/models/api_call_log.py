"""
Registro de llamadas a APIs externas para monitorización (Yahoo, exchangerate, etc.).
"""
from datetime import datetime
from app import db


class ApiCallLog(db.Model):
    __tablename__ = 'api_call_log'

    id = db.Column(db.Integer, primary_key=True)
    api_name = db.Column(db.String(50), nullable=False, index=True)  # 'exchangerate', 'yahoo_chart', 'yahoo_quote'
    endpoint_or_operation = db.Column(db.String(255), nullable=True)  # URL o nombre de operación
    called_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    response_status = db.Column(db.Integer, nullable=True)  # 200, 404, etc.
    value_reported = db.Column(db.JSON, nullable=True)  # ej: {"currencies": 42}, {"price": 150.5}
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # null = sistema
    extra = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<ApiCallLog {self.api_name} @ {self.called_at}>'
