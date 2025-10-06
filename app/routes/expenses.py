"""
Blueprint para gestión de gastos
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models import ExpenseCategory, Expense
from app.forms import ExpenseCategoryForm, ExpenseForm
from app.utils.recurrence import create_recurrence_instances

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


# ==================== CATEGORÍAS ====================

@expenses_bp.route('/categories')
@login_required
def categories():
    """Listar categorías de gastos"""
    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()
    
    return render_template(
        'expenses/categories.html',
        categories=categories
    )


@expenses_bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
def new_category():
    """Crear nueva categoría"""
    form = ExpenseCategoryForm()
    
    # Cargar categorías para el selector de padre
    form.parent_id.choices = [(0, '-- Sin categoría padre --')] + [
        (c.id, c.name) for c in ExpenseCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=None  # Solo categorías de nivel superior
        ).order_by(ExpenseCategory.name).all()
    ]
    
    if form.validate_on_submit():
        category = ExpenseCategory(
            name=form.name.data,
            icon=form.icon.data or '💰',
            color=form.color.data,
            user_id=current_user.id,
            parent_id=form.parent_id.data if form.parent_id.data != 0 else None
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash(f'Categoría "{category.name}" creada exitosamente', 'success')
        return redirect(url_for('expenses.categories'))
    
    return render_template('expenses/category_form.html', form=form, title='Nueva Categoría')


@expenses_bp.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    """Editar categoría"""
    category = ExpenseCategory.query.get_or_404(id)
    
    # Verificar que pertenece al usuario
    if category.user_id != current_user.id:
        flash('No tienes permiso para editar esta categoría', 'error')
        return redirect(url_for('expenses.categories'))
    
    form = ExpenseCategoryForm(obj=category)
    
    # Cargar categorías para el selector de padre (excluyendo la actual y sus hijos)
    form.parent_id.choices = [(0, '-- Sin categoría padre --')] + [
        (c.id, c.name) for c in ExpenseCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=None
        ).filter(ExpenseCategory.id != id).order_by(ExpenseCategory.name).all()
    ]
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.icon = form.icon.data or '💰'
        category.color = form.color.data
        category.parent_id = form.parent_id.data if form.parent_id.data != 0 else None
        
        db.session.commit()
        
        flash(f'Categoría "{category.name}" actualizada', 'success')
        return redirect(url_for('expenses.categories'))
    
    return render_template(
        'expenses/category_form.html',
        form=form,
        title='Editar Categoría',
        category=category
    )


@expenses_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    """Eliminar categoría"""
    category = ExpenseCategory.query.get_or_404(id)
    
    if category.user_id != current_user.id:
        flash('No tienes permiso para eliminar esta categoría', 'error')
        return redirect(url_for('expenses.categories'))
    
    # Verificar si tiene gastos asociados
    if category.expenses.count() > 0:
        flash(f'No se puede eliminar "{category.name}" porque tiene gastos asociados', 'error')
        return redirect(url_for('expenses.categories'))
    
    name = category.name
    db.session.delete(category)
    db.session.commit()
    
    flash(f'Categoría "{name}" eliminada', 'info')
    return redirect(url_for('expenses.categories'))


# ==================== GASTOS ====================

@expenses_bp.route('/')
@login_required
def list():
    """Listar gastos"""
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    
    # Query base
    query = Expense.query.filter_by(user_id=current_user.id)
    
    # Filtrar por categoría si se especifica
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # Ordenar por fecha descendente (más recientes primero)
    query = query.order_by(Expense.date.desc())
    
    # Paginar
    expenses = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    # Obtener categorías para el filtro
    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()
    
    return render_template(
        'expenses/list.html',
        expenses=expenses,
        categories=categories,
        selected_category=category_id
    )


@expenses_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo gasto"""
    form = ExpenseForm()
    
    # Cargar categorías
    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()
    
    if not categories:
        flash('Primero debes crear al menos una categoría de gastos', 'warning')
        return redirect(url_for('expenses.new_category'))
    
    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]
    
    if form.validate_on_submit():
        # Crear instancia base (sin guardar aún)
        base_expense = Expense(
            user_id=current_user.id,
            category_id=form.category_id.data,
            amount=form.amount.data,
            description=form.description.data,
            date=form.date.data,
            notes=form.notes.data,
            is_recurring=form.is_recurring.data,
            recurrence_frequency=form.recurrence_frequency.data if form.is_recurring.data else None,
            recurrence_end_date=form.recurrence_end_date.data if form.is_recurring.data else None
        )
        
        # Generar instancias recurrentes si aplica
        expense_instances = create_recurrence_instances(Expense, base_expense, current_user.id)
        
        # Guardar todas las instancias
        for expense in expense_instances:
            db.session.add(expense)
        
        db.session.commit()
        
        # Mensaje según cantidad de instancias generadas
        if len(expense_instances) > 1:
            flash(f'✅ {len(expense_instances)} gastos recurrentes registrados (€{base_expense.amount:.2f} cada uno)', 'success')
        else:
            flash(f'Gasto de €{base_expense.amount:.2f} registrado', 'success')
        
        return redirect(url_for('expenses.list'))
    
    return render_template('expenses/form.html', form=form, title='Nuevo Gasto')


@expenses_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Editar gasto"""
    expense = Expense.query.get_or_404(id)
    
    if expense.user_id != current_user.id:
        flash('No tienes permiso para editar este gasto', 'error')
        return redirect(url_for('expenses.list'))
    
    form = ExpenseForm(obj=expense)
    
    # Cargar categorías
    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()
    
    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]
    
    if form.validate_on_submit():
        expense.category_id = form.category_id.data
        expense.amount = form.amount.data
        expense.description = form.description.data
        expense.date = form.date.data
        expense.notes = form.notes.data
        expense.is_recurring = form.is_recurring.data
        expense.recurrence_frequency = form.recurrence_frequency.data if form.is_recurring.data else None
        expense.recurrence_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
        
        db.session.commit()
        
        flash(f'Gasto actualizado', 'success')
        return redirect(url_for('expenses.list'))
    
    return render_template(
        'expenses/form.html',
        form=form,
        title='Editar Gasto',
        expense=expense
    )


@expenses_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Eliminar gasto"""
    expense = Expense.query.get_or_404(id)
    
    if expense.user_id != current_user.id:
        flash('No tienes permiso para eliminar este gasto', 'error')
        return redirect(url_for('expenses.list'))
    
    db.session.delete(expense)
    db.session.commit()
    
    flash('Gasto eliminado', 'info')
    return redirect(url_for('expenses.list'))

