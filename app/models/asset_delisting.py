"""
Modelo para registrar activos que han dejado de cotizar (adquisición en efectivo, quiebra).
Permite generar automáticamente operaciones de venta cuando el usuario tenía posiciones.
"""
from datetime import datetime
from app import db

DELISTING_TYPES = ['CASH_ACQUISITION', 'BANKRUPTCY']


class AssetDelisting(db.Model):
    """
    Registro de baja de cotización de un activo.
    Fecha y precio a los que se considera cerrada la posición (adquisición, quiebra).
    """
    __tablename__ = 'asset_delistings'

    id = db.Column(db.Integer, primary_key=True)
    asset_registry_id = db.Column(db.Integer, db.ForeignKey('asset_registry.id'), nullable=False)

    # Fecha efectiva de la baja (cuando se liquida la posición)
    delisting_date = db.Column(db.Date, nullable=False, index=True)
    # Precio por acción en la liquidación (0 para quiebra)
    delisting_price = db.Column(db.Float, nullable=False, default=0.0)
    delisting_currency = db.Column(db.String(3), nullable=False, default='EUR')
    # Tipo: CASH_ACQUISITION, BANKRUPTCY
    delisting_type = db.Column(db.String(30), nullable=False, default='CASH_ACQUISITION')
    notes = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación
    asset_registry = db.relationship('AssetRegistry', backref=db.backref('delistings', lazy=True))

    def __repr__(self):
        return f"AssetDelisting(registry_id={self.asset_registry_id}, date={self.delisting_date}, price={self.delisting_price})"
