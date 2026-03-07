"""
Modelos para el módulo Inmuebles (Real Estate)
"""
from datetime import date, datetime
from app import db


PROPERTY_TYPES = [
    ('terreno', 'Terreno'),
    ('casa', 'Casa'),
    ('piso', 'Piso'),
    ('garaje', 'Garaje'),
    ('oficina', 'Oficina'),
]

PROPERTY_ICONS = {
    'terreno': '🏞️',
    'casa': '🏠',
    'piso': '🏢',
    'garaje': '🅿️',
    'oficina': '🏛️',
}


def get_property_icon(property_type: str) -> str:
    """Emoji por tipo de inmueble"""
    return PROPERTY_ICONS.get(property_type, '🏠')


class RealEstateProperty(db.Model):
    """Inmueble registrado por el usuario"""
    __tablename__ = 'real_estate_properties'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    property_type = db.Column(db.String(20), nullable=False)  # terreno, casa, piso, garaje, oficina
    address = db.Column(db.String(255), nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('real_estate_properties', lazy='dynamic'))
    valuations = db.relationship(
        'PropertyValuation',
        backref='property',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='PropertyValuation.year'
    )
    debt_plan = db.relationship(
        'DebtPlan',
        backref='real_estate_property',
        uselist=False,
        foreign_keys='DebtPlan.property_id'
    )

    def get_icon(self) -> str:
        return get_property_icon(self.property_type)

    def get_estimated_value(self) -> float:
        """Última tasación hasta año actual, o precio de compra"""
        current_year = date.today().year
        last_val = PropertyValuation.query.filter(
            PropertyValuation.property_id == self.id,
            PropertyValuation.year <= current_year
        ).order_by(PropertyValuation.year.desc()).first()
        return last_val.value if last_val else self.purchase_price

    def get_valuation_year(self) -> int:
        """Año de la última tasación (hasta año actual)"""
        current_year = date.today().year
        last_val = PropertyValuation.query.filter(
            PropertyValuation.property_id == self.id,
            PropertyValuation.year <= current_year
        ).order_by(PropertyValuation.year.desc()).first()
        return last_val.year if last_val else self.purchase_date.year

    def get_revaluation_since_purchase(self) -> tuple:
        """Revalorización desde compra: (absoluta €, porcentaje %)"""
        val = self.get_estimated_value()
        diff = val - self.purchase_price
        pct = (diff / self.purchase_price * 100) if self.purchase_price else 0
        return diff, pct

    def has_mortgage(self) -> bool:
        from app.models.debt_plan import DebtPlan
        return DebtPlan.query.filter_by(property_id=self.id, status='ACTIVE').first() is not None


class PropertyValuation(db.Model):
    """Tasación anual de un inmueble"""
    __tablename__ = 'property_valuations'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('real_estate_properties.id', ondelete='CASCADE'), nullable=False)

    year = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)  # EUR

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
