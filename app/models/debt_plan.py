"""
Modelo para planes de deuda (pagos a plazos)
"""
from datetime import datetime
from app import db


class DebtPlan(db.Model):
    """Plan de deuda: gasto pagado a plazos con cuotas mensuales"""
    
    __tablename__ = 'debt_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=False)
    
    # Datos del plan
    name = db.Column(db.String(255), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    months = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    
    # Estado
    status = db.Column(
        db.String(20),
        default='ACTIVE',
        nullable=False
    )  # ACTIVE, PAID_OFF, CANCELLED
    
    notes = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref='debt_plans')
    category = db.relationship('ExpenseCategory', backref='debt_plans')
    installment_expenses = db.relationship(
        'Expense',
        backref='debt_plan',
        lazy='dynamic',
        foreign_keys='Expense.debt_plan_id'
    )
    
    def __repr__(self):
        return f'<DebtPlan {self.name}: €{self.total_amount} / {self.months} meses>'
    
    @property
    def monthly_payment(self):
        """Cuota mensual (sin interés en v1)"""
        if self.months <= 0:
            return 0.0
        return round(self.total_amount / self.months, 2)
    
    def to_dict(self):
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'name': self.name,
            'total_amount': self.total_amount,
            'months': self.months,
            'monthly_payment': self.monthly_payment,
            'start_date': self.start_date.isoformat(),
            'status': self.status,
            'category': self.category.name if self.category else None,
        }
