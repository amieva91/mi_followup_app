"""
Planificación de gastos: configuración, categorías fijas proyectadas y objetivos (metas).
"""
from datetime import datetime

from app import db


class SpendingPlanSettings(db.Model):
    """Una fila por usuario: DSR máximo y horizonte."""

    __tablename__ = "spending_plan_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    max_dsr_percent = db.Column(db.Float, nullable=False, default=35.0)
    horizon_months = db.Column(db.Integer, nullable=False, default=12)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("spending_plan_settings", uselist=False))


class SpendingPlanFixedCategory(db.Model):
    """Categorías de gasto que el usuario marca como fijas para la proyección."""

    __tablename__ = "spending_plan_fixed_categories"
    __table_args__ = (
        db.UniqueConstraint("user_id", "expense_category_id", name="uq_sp_fixed_cat_user_cat"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    expense_category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="spending_plan_fixed_categories")
    category = db.relationship("ExpenseCategory", backref="spending_plan_fixed_entries")


class SpendingPlanGoal(db.Model):
    """Objetivo de gasto / compra planificada (hipoteca, reforma, etc.)."""

    __tablename__ = "spending_plan_goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    goal_type = db.Column(db.String(32), nullable=False, default="generic")
    priority = db.Column(db.Integer, nullable=False, default=3)  # 1 = máxima
    amount_total = db.Column(db.Float, nullable=False, default=0.0)
    target_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    extra_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref="spending_plan_goals")
