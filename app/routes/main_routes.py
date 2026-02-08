"""
Rutas principales de la aplicación
"""
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import func, extract
from app.routes import main_bp
from app import db
from app.models import Expense, Income


@main_bp.route('/')
def index():
    """Página de inicio"""
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal (requiere login)"""
    # Obtener mes y año actuales
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    # Calcular gastos del mes actual
    expenses_this_month = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).scalar() or 0
    
    # Calcular ingresos del mes actual
    incomes_this_month = db.session.query(func.sum(Income.amount)).filter(
        Income.user_id == current_user.id,
        extract('month', Income.date) == current_month,
        extract('year', Income.date) == current_year
    ).scalar() or 0
    
    # Balance del mes (ingresos - gastos)
    balance_this_month = incomes_this_month - expenses_this_month
    
    # Últimos gastos (top 5) - excluir cuotas futuras de deuda
    today = date.today()
    recent_expenses = Expense.query.filter(
        Expense.user_id == current_user.id
    ).filter(
        db.or_(
            Expense.debt_plan_id.is_(None),
            Expense.date <= today
        )
    ).order_by(Expense.date.desc()).limit(5).all()
    
    # Últimos ingresos (top 5)
    recent_incomes = Income.query.filter_by(
        user_id=current_user.id
    ).order_by(Income.date.desc()).limit(5).all()
    
    return render_template(
        'dashboard.html',
        expenses_this_month=expenses_this_month,
        incomes_this_month=incomes_this_month,
        balance_this_month=balance_this_month,
        recent_expenses=recent_expenses,
        recent_incomes=recent_incomes,
        current_month_name=now.strftime('%B')
    )


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'app': 'FollowUp',
        'version': '2.0.0'
    }, 200

