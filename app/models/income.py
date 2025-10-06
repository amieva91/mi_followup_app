"""
Modelos para gestión de ingresos variables
"""
from datetime import datetime
from app import db


class IncomeCategory(db.Model):
    """Categorías de ingresos variables"""
    
    __tablename__ = 'income_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='💵')  # Emoji o nombre de icono
    color = db.Column(db.String(20), default='green')  # Color Tailwind
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones
    user = db.relationship('User', backref='income_categories')
    incomes = db.relationship('Income', backref='category', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<IncomeCategory {self.name}>'
    
    def total_income(self, start_date=None, end_date=None):
        """Total de ingresos en esta categoría"""
        query = self.incomes
        
        if start_date:
            query = query.filter(Income.date >= start_date)
        if end_date:
            query = query.filter(Income.date <= end_date)
        
        return db.session.query(db.func.sum(Income.amount)).filter(
            Income.category_id == self.id,
            Income.date >= start_date if start_date else True,
            Income.date <= end_date if end_date else True
        ).scalar() or 0.0


class Income(db.Model):
    """Ingresos variables (freelance, bonos, etc.)"""
    
    __tablename__ = 'incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('income_categories.id'), nullable=False)
    
    # Detalles del ingreso
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Recurrencia
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    recurrence_frequency = db.Column(
        db.String(20), 
        nullable=True
    )  # 'weekly', 'monthly', 'yearly'
    recurrence_end_date = db.Column(db.Date, nullable=True)
    recurrence_group_id = db.Column(db.String(36), nullable=True)  # UUID para agrupar series
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref='incomes')
    
    def __repr__(self):
        return f'<Income {self.description}: €{self.amount}>'
    
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
        """Total de ingresos en un período"""
        return db.session.query(db.func.sum(Income.amount)).filter(
            Income.user_id == user_id,
            Income.date >= start_date,
            Income.date <= end_date
        ).scalar() or 0.0
    
    @staticmethod
    def get_by_category(user_id, start_date, end_date):
        """Ingresos agrupados por categoría"""
        results = db.session.query(
            IncomeCategory.name,
            IncomeCategory.icon,
            IncomeCategory.color,
            db.func.sum(Income.amount).label('total')
        ).join(Income).filter(
            Income.user_id == user_id,
            Income.date >= start_date,
            Income.date <= end_date
        ).group_by(IncomeCategory.id).all()
        
        return [
            {
                'category': r.name,
                'icon': r.icon,
                'color': r.color,
                'total': float(r.total)
            }
            for r in results
        ]

