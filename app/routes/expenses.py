"""
Blueprint para gestión de gastos
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from datetime import datetime, date
from app import db
from app.models import ExpenseCategory, Expense
from app.forms import ExpenseCategoryForm, ExpenseForm
from app.utils.recurrence import create_recurrence_instances
from app.services.category_helpers import filter_editable_categories, is_ajustes_category
from app.services.income_expense_aggregator import (
    get_expense_category_summary_with_adjustment,
    get_expense_monthly_totals_with_adjustment,
    get_synthetic_expense_entries_by_month,
)
from app.services.summary_metrics_service import get_expense_summary_metrics
from app.services.dashboard_summary_cache import DashboardSummaryCacheService

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


def _touch_dashboard_for_expense_dates(user_id, dates):
    """Sincroniza caché del dashboard (barras, histórico) tras cambiar gastos."""
    if dates:
        DashboardSummaryCacheService.touch_for_dates(user_id, dates=dates)


# ==================== CATEGORÍAS ====================

@expenses_bp.route('/categories')
@login_required
def categories():
    """Listar categorías de gastos (agrupadas jerárquicamente)"""
    # Obtener categorías principales ordenadas alfabéticamente
    parent_categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None
    ).order_by(ExpenseCategory.name).all()
    
    # Construir lista con categorías padre e hijos
    categories = []
    for parent in parent_categories:
        categories.append(parent)
        # Agregar subcategorías ordenadas alfabéticamente
        subcategories = ExpenseCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=parent.id
        ).order_by(ExpenseCategory.name).all()
        categories.extend(subcategories)
    
    return render_template(
        'expenses/categories.html',
        categories=categories
    )


@expenses_bp.route('/categories/quick-create', methods=['POST'])
@login_required
def quick_create_category():
    """API: crear categoría de gasto desde modal, devuelve JSON."""
    name = request.form.get('name') or request.json.get('name') if request.is_json else request.form.get('name')
    icon = request.form.get('icon', '💰') or '💰'
    parent_id = request.form.get('parent_id', type=int) or 0
    if not name or not name.strip():
        return jsonify({'error': 'El nombre es requerido'}), 400
    if parent_id:
        parent = ExpenseCategory.query.filter_by(id=parent_id, user_id=current_user.id).first()
        if not parent:
            return jsonify({'error': 'Categoría padre no válida'}), 400
    cat = ExpenseCategory(
        name=name.strip(),
        icon=icon or '💰',
        color='gray',
        user_id=current_user.id,
        parent_id=parent_id if parent_id else None
    )
    db.session.add(cat)
    db.session.commit()
    label = f"{cat.icon} {cat.full_name}"
    return jsonify({'id': cat.id, 'name': cat.name, 'icon': cat.icon, 'full_name': cat.full_name, 'label': label})


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
        if form.name.data.strip() == 'Ajustes':
            flash('El nombre "Ajustes" está reservado para el sistema', 'warning')
            return redirect(url_for('expenses.new_category'))
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
    
    if is_ajustes_category(category):
        flash('La categoría Ajustes está reservada para el sistema y no puede editarse', 'warning')
        return redirect(url_for('expenses.categories'))
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
        if form.name.data.strip() == 'Ajustes':
            flash('El nombre "Ajustes" está reservado para el sistema', 'warning')
            return redirect(url_for('expenses.categories'))
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
    
    if is_ajustes_category(category):
        flash('La categoría Ajustes está reservada para el sistema y no puede eliminarse', 'warning')
        return redirect(url_for('expenses.categories'))
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
    from datetime import date
    
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    
    # Query base (joinedload para asegurar categoría actualizada tras ediciones)
    query = Expense.query.options(joinedload(Expense.category)).filter_by(user_id=current_user.id)
    
    # Cuotas de deuda: solo mostrar las ya vencidas (fecha <= hoy)
    today = date.today()
    query = query.filter(
        db.or_(
            Expense.debt_plan_id.is_(None),
            Expense.date <= today
        )
    )
    
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

    # Resumen por categoría (12 meses, jerárquico) incluyendo ajuste de reconciliación
    category_summary = get_expense_category_summary_with_adjustment(current_user.id, months=12)
    # Totales mensuales (12 meses) para gráfico de barras incluyendo ajuste
    monthly_totals = get_expense_monthly_totals_with_adjustment(current_user.id, months=12)
    # Métricas de resumen (Fase 6)
    summary_metrics = get_expense_summary_metrics(current_user.id, months=12)
    # Entradas sintéticas por mes (Ajustes y Stock Market) - todo el histórico
    synthetic_entries = get_synthetic_expense_entries_by_month(current_user.id, months=None)
    
    # Calcular meses con entradas sintéticas pero SIN gastos reales
    # para mostrarlos como filas independientes en la tabla
    orphan_synthetic_entries = []
    if synthetic_entries:
        # Obtener todos los meses únicos que tienen gastos reales
        months_with_real_expenses = set()
        all_expenses_query = Expense.query.filter_by(user_id=current_user.id).with_entities(
            db.func.extract('year', Expense.date).label('year'),
            db.func.extract('month', Expense.date).label('month')
        ).distinct().all()
        for row in all_expenses_query:
            months_with_real_expenses.add((int(row.year), int(row.month)))
        
        # Identificar meses sintéticos huérfanos (sin gastos reales)
        for (year, month), data in sorted(synthetic_entries.items(), reverse=True):
            if (year, month) not in months_with_real_expenses:
                orphan_synthetic_entries.append({
                    'year': year,
                    'month': month,
                    'month_label': data['month_label'],
                    'ajuste': data['ajuste'],
                    'stock_market': data['stock_market'],
                    'include_adjustment_in_metrics': data.get(
                        'include_adjustment_in_metrics', True
                    ),
                })

    return render_template(
        'expenses/list.html',
        expenses=expenses,
        categories=categories,
        selected_category=category_id,
        category_summary=category_summary,
        monthly_totals=monthly_totals,
        summary_metrics=summary_metrics,
        synthetic_entries=synthetic_entries,
        orphan_synthetic_entries=orphan_synthetic_entries
    )


@expenses_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo gasto"""
    form = ExpenseForm()
    
    # Cargar categorías (excluir Ajustes, reservada para el sistema)
    categories = filter_editable_categories(
        ExpenseCategory.query.filter_by(user_id=current_user.id).order_by(ExpenseCategory.name).all()
    )
    
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
        _touch_dashboard_for_expense_dates(
            current_user.id,
            [e.date for e in expense_instances if e.date],
        )
        
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
    """Editar gasto (si es recurrente, edita toda la serie)"""
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
    
    # Verificar si es parte de una serie recurrente
    is_part_of_series = expense.is_recurring and expense.recurrence_group_id
    
    if form.validate_on_submit():
        old_date = expense.date
        # Detectar si cambió de puntual a recurrente
        was_not_recurring = not expense.is_recurring
        will_be_recurring = form.is_recurring.data
        
        if was_not_recurring and will_be_recurring:
            # Cambió de puntual a recurrente: generar nuevas instancias
            temp_expense = Expense(
                user_id=current_user.id,
                category_id=form.category_id.data,
                amount=form.amount.data,
                description=form.description.data,
                date=form.date.data,
                notes=form.notes.data,
                is_recurring=True,
                recurrence_frequency=form.recurrence_frequency.data,
                recurrence_end_date=form.recurrence_end_date.data
            )
            
            expense_instances = create_recurrence_instances(Expense, temp_expense, current_user.id)
            db.session.delete(expense)
            
            for new_expense in expense_instances:
                db.session.add(new_expense)
            
            db.session.commit()
            _touch_dashboard_for_expense_dates(
                current_user.id,
                [old_date] + [e.date for e in expense_instances if e.date],
            )
            flash(f'✅ Gasto convertido a recurrente: {len(expense_instances)} entradas generadas', 'success')
        
        elif is_part_of_series:
            # Es parte de una serie: actualizar TODA la serie
            series_expenses = Expense.query.filter_by(
                user_id=current_user.id,
                recurrence_group_id=expense.recurrence_group_id
            ).all()
            series_dates_for_cache = [e.date for e in series_expenses if e.date]
            
            # Si la fecha de fin cambió a una anterior, eliminar entradas posteriores
            new_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            deleted_count = 0
            
            for series_expense in series_expenses[:]:  # Copia para iterar mientras modificamos
                # Si hay nueva fecha de fin y esta entrada es posterior, eliminarla
                if new_end_date and series_expense.date > new_end_date:
                    db.session.delete(series_expense)
                    series_expenses.remove(series_expense)
                    deleted_count += 1
                else:
                    # Actualizar la entrada
                    series_expense.category_id = form.category_id.data
                    series_expense.amount = form.amount.data
                    series_expense.description = form.description.data
                    series_expense.notes = form.notes.data
                    series_expense.recurrence_frequency = form.recurrence_frequency.data if form.is_recurring.data else None
                    series_expense.recurrence_end_date = new_end_date
                    # NO actualizar la fecha, cada entrada mantiene su fecha
            
            db.session.commit()
            _touch_dashboard_for_expense_dates(current_user.id, series_dates_for_cache)
            
            if deleted_count > 0:
                flash(f'✅ Serie actualizada: {len(series_expenses)} gastos actualizados, {deleted_count} eliminados', 'success')
            else:
                flash(f'✅ Serie completa actualizada ({len(series_expenses)} gastos)', 'success')
        
        else:
            # Actualización normal (gasto puntual)
            expense.category_id = form.category_id.data
            expense.amount = form.amount.data
            expense.description = form.description.data
            expense.date = form.date.data
            expense.notes = form.notes.data
            expense.is_recurring = form.is_recurring.data
            expense.recurrence_frequency = form.recurrence_frequency.data if form.is_recurring.data else None
            expense.recurrence_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            
            db.session.commit()
            _touch_dashboard_for_expense_dates(
                current_user.id,
                [d for d in (old_date, expense.date) if d],
            )
            flash(f'Gasto actualizado', 'success')
        
        return redirect(url_for('expenses.list'))
    
    # Agregar información en el título si es parte de una serie
    title = 'Editar Serie de Gastos' if is_part_of_series else 'Editar Gasto'
    
    return render_template(
        'expenses/form.html',
        form=form,
        title=title,
        expense=expense,
        is_part_of_series=is_part_of_series
    )


@expenses_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Eliminar gasto"""
    expense = Expense.query.get_or_404(id)
    
    if expense.user_id != current_user.id:
        flash('No tienes permiso para eliminar este gasto', 'error')
        return redirect(url_for('expenses.list'))
    
    # Verificar si es parte de una serie recurrente
    delete_series = request.form.get('delete_series') == 'true'
    
    if expense.is_recurring and expense.recurrence_group_id and delete_series:
        # Eliminar toda la serie
        series_dates = [
            e.date
            for e in Expense.query.filter_by(
                user_id=current_user.id,
                recurrence_group_id=expense.recurrence_group_id,
            ).all()
            if e.date
        ]
        count = Expense.query.filter_by(
            user_id=current_user.id,
            recurrence_group_id=expense.recurrence_group_id
        ).delete()
        
        db.session.commit()
        _touch_dashboard_for_expense_dates(current_user.id, series_dates)
        flash(f'✅ Serie completa eliminada ({count} gastos)', 'info')
    else:
        # Eliminar solo esta entrada
        del_date = expense.date
        db.session.delete(expense)
        db.session.commit()
        _touch_dashboard_for_expense_dates(current_user.id, [del_date] if del_date else [])
        flash('Gasto eliminado', 'info')
    
    return redirect(url_for('expenses.list'))

