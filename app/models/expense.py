"""
Modelos para gestión de gastos
"""
from datetime import datetime, timedelta
from app import db


class ExpenseCategory(db.Model):
    """Categorías de gastos (jerárquicas)"""
    
    __tablename__ = 'expense_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='💰')  # Emoji o nombre de icono
    color = db.Column(db.String(20), default='gray')  # Color Tailwind
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Para jerarquía (categorías padre/hijo)
    parent_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones
    user = db.relationship('User', backref='expense_categories')
    expenses = db.relationship('Expense', backref='category', lazy='dynamic', cascade='all, delete-orphan')
    
    # Auto-referencia para jerarquía
    children = db.relationship(
        'ExpenseCategory',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'
    
    @property
    def full_name(self):
        """Nombre completo con padre (si existe)"""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def total_expenses(self, start_date=None, end_date=None):
        """Total de gastos en esta categoría"""
        query = self.expenses
        
        if start_date:
            query = query.filter(Expense.date >= start_date)
        if end_date:
            query = query.filter(Expense.date <= end_date)
        
        return db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.category_id == self.id,
            Expense.date >= start_date if start_date else True,
            Expense.date <= end_date if end_date else True
        ).scalar() or 0.0


class Expense(db.Model):
    """Gastos individuales"""
    
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=False)
    
    # Detalles del gasto
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Recurrencia
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    recurrence_frequency = db.Column(
        db.String(20), 
        nullable=True
    )  # 'daily', 'weekly', 'monthly', 'yearly'
    recurrence_end_date = db.Column(db.Date, nullable=True)
    recurrence_group_id = db.Column(db.String(36), nullable=True)  # UUID para agrupar series
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref='expenses')
    
    def __repr__(self):
        return f'<Expense {self.description}: €{self.amount}>'
    
    def to_dict(self):
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'category': self.category.name,
            'category_icon': self.category.icon,
            'category_color': self.category.color,
            'amount': self.amount,
            'description': self.description,
            'date': self.date.isoformat(),
            'notes': self.notes,
            'is_recurring': self.is_recurring,
            'recurrence_frequency': self.recurrence_frequency,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_total_by_period(user_id, start_date, end_date):
        """Total de gastos en un período"""
        return db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.date >= start_date,
            Expense.date <= end_date
        ).scalar() or 0.0
    
    @staticmethod
    def get_by_category(user_id, start_date, end_date):
        """Gastos agrupados por categoría"""
        results = db.session.query(
            ExpenseCategory.name,
            ExpenseCategory.icon,
            ExpenseCategory.color,
            db.func.sum(Expense.amount).label('total')
        ).join(Expense).filter(
            Expense.user_id == user_id,
            Expense.date >= start_date,
            Expense.date <= end_date
        ).group_by(ExpenseCategory.id).all()
        
        return [
            {
                'category': r.name,
                'icon': r.icon,
                'color': r.color,
                'total': float(r.total)
            }
            for r in results
        ]

