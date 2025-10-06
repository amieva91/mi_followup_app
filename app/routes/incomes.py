"""
Blueprint para gestión de ingresos
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import IncomeCategory, Income
from app.forms import IncomeCategoryForm, IncomeForm
from app.utils.recurrence import create_recurrence_instances

incomes_bp = Blueprint('incomes', __name__, url_prefix='/incomes')


# ==================== CATEGORÍAS ====================

@incomes_bp.route('/categories')
@login_required
def categories():
    """Listar categorías de ingresos"""
    categories = IncomeCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(IncomeCategory.name).all()
    
    return render_template(
        'incomes/categories.html',
        categories=categories
    )


@incomes_bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
def new_category():
    """Crear nueva categoría"""
    form = IncomeCategoryForm()
    
    if form.validate_on_submit():
        category = IncomeCategory(
            name=form.name.data,
            icon=form.icon.data or '💵',
            color=form.color.data,
            user_id=current_user.id
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash(f'Categoría "{category.name}" creada exitosamente', 'success')
        return redirect(url_for('incomes.categories'))
    
    return render_template('incomes/category_form.html', form=form, title='Nueva Categoría')


@incomes_bp.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    """Editar categoría"""
    category = IncomeCategory.query.get_or_404(id)
    
    if category.user_id != current_user.id:
        flash('No tienes permiso para editar esta categoría', 'error')
        return redirect(url_for('incomes.categories'))
    
    form = IncomeCategoryForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.icon = form.icon.data or '💵'
        category.color = form.color.data
        
        db.session.commit()
        
        flash(f'Categoría "{category.name}" actualizada', 'success')
        return redirect(url_for('incomes.categories'))
    
    return render_template(
        'incomes/category_form.html',
        form=form,
        title='Editar Categoría',
        category=category
    )


@incomes_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    """Eliminar categoría"""
    category = IncomeCategory.query.get_or_404(id)
    
    if category.user_id != current_user.id:
        flash('No tienes permiso para eliminar esta categoría', 'error')
        return redirect(url_for('incomes.categories'))
    
    # Verificar si tiene ingresos asociados
    if category.incomes.count() > 0:
        flash(f'No se puede eliminar "{category.name}" porque tiene ingresos asociados', 'error')
        return redirect(url_for('incomes.categories'))
    
    name = category.name
    db.session.delete(category)
    db.session.commit()
    
    flash(f'Categoría "{name}" eliminada', 'info')
    return redirect(url_for('incomes.categories'))


# ==================== INGRESOS ====================

@incomes_bp.route('/')
@login_required
def list():
    """Listar ingresos"""
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    
    # Query base
    query = Income.query.filter_by(user_id=current_user.id)
    
    # Filtrar por categoría si se especifica
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # Ordenar por fecha descendente
    query = query.order_by(Income.date.desc())
    
    # Paginar
    incomes = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    # Obtener categorías para el filtro
    categories = IncomeCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(IncomeCategory.name).all()
    
    return render_template(
        'incomes/list.html',
        incomes=incomes,
        categories=categories,
        selected_category=category_id
    )


@incomes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo ingreso"""
    form = IncomeForm()
    
    # Cargar categorías
    categories = IncomeCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(IncomeCategory.name).all()
    
    if not categories:
        flash('Primero debes crear al menos una categoría de ingresos', 'warning')
        return redirect(url_for('incomes.new_category'))
    
    form.category_id.choices = [(c.id, f"{c.icon} {c.name}") for c in categories]
    
    if form.validate_on_submit():
        # Crear instancia base (sin guardar aún)
        base_income = Income(
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
        income_instances = create_recurrence_instances(Income, base_income, current_user.id)
        
        # Guardar todas las instancias
        for income in income_instances:
            db.session.add(income)
        
        db.session.commit()
        
        # Mensaje según cantidad de instancias generadas
        if len(income_instances) > 1:
            flash(f'✅ {len(income_instances)} ingresos recurrentes registrados (€{base_income.amount:.2f} cada uno)', 'success')
        else:
            flash(f'Ingreso de €{base_income.amount:.2f} registrado', 'success')
        
        return redirect(url_for('incomes.list'))
    
    return render_template('incomes/form.html', form=form, title='Nuevo Ingreso')


@incomes_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Editar ingreso"""
    income = Income.query.get_or_404(id)
    
    if income.user_id != current_user.id:
        flash('No tienes permiso para editar este ingreso', 'error')
        return redirect(url_for('incomes.list'))
    
    form = IncomeForm(obj=income)
    
    # Cargar categorías
    categories = IncomeCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(IncomeCategory.name).all()
    
    form.category_id.choices = [(c.id, f"{c.icon} {c.name}") for c in categories]
    
    if form.validate_on_submit():
        income.category_id = form.category_id.data
        income.amount = form.amount.data
        income.description = form.description.data
        income.date = form.date.data
        income.notes = form.notes.data
        income.is_recurring = form.is_recurring.data
        income.recurrence_frequency = form.recurrence_frequency.data if form.is_recurring.data else None
        income.recurrence_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
        
        db.session.commit()
        
        flash(f'Ingreso actualizado', 'success')
        return redirect(url_for('incomes.list'))
    
    return render_template(
        'incomes/form.html',
        form=form,
        title='Editar Ingreso',
        income=income
    )


@incomes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Eliminar ingreso"""
    income = Income.query.get_or_404(id)
    
    if income.user_id != current_user.id:
        flash('No tienes permiso para eliminar este ingreso', 'error')
        return redirect(url_for('incomes.list'))
    
    db.session.delete(income)
    db.session.commit()
    
    flash('Ingreso eliminado', 'info')
    return redirect(url_for('incomes.list'))

