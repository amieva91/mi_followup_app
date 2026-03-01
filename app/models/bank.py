"""
Modelos para gestión de cuentas bancarias y saldos mensuales
"""
from datetime import datetime
from app import db


class Bank(db.Model):
    """Entidad bancaria del usuario"""
    __tablename__ = 'banks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), default='🏦')
    color = db.Column(db.String(20), default='blue')

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('banks', lazy=True))
    balances = db.relationship('BankBalance', backref='bank', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"Bank('{self.name}')"


class BankBalance(db.Model):
    """Saldo por banco y mes"""
    __tablename__ = 'bank_balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey('banks.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('bank_id', 'year', 'month', name='uq_bank_balance_per_month'),
    )

    user = db.relationship('User', backref=db.backref('bank_balances', lazy=True))

    def __repr__(self):
        return f"BankBalance(bank_id={self.bank_id}, {self.year}-{self.month:02d}, {self.amount})"
