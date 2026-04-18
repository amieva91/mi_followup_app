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
from app.utils.recurrence_edit_scope import RECURRENCE_EDIT_SCOPES, parse_pivot_date
from app.services.category_helpers import (
    AJUSTES_CATEGORY_NAME,
    STOCK_MARKET_CATEGORY_NAME,
    filter_editable_categories,
    is_ajustes_category,
)
from app.services.income_expense_aggregator import (
    get_expense_category_summary_with_adjustment,
    get_expense_monthly_totals_with_adjustment,
    get_synthetic_expense_entries_by_month,
)
from app.services.summary_metrics_service import get_expense_summary_metrics
from app.services.dashboard_summary_cache import DashboardSummaryCacheService

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


def _expense_needs_recurrence_scope_choice(expense):
    """Serie recurrente editable por ámbito (no cuotas de plan de deuda)."""
    return bool(
        expense.is_recurring
        and expense.recurrence_group_id
        and not expense.debt_plan_id
    )


def _pivot_belongs_to_expense_series(user_id, group_id, pivot):
    return (
        Expense.query.filter(
            Expense.user_id == user_id,
            Expense.recurrence_group_id == group_id,
            Expense.date == pivot,
        ).first()
        is not None
    )


def _apply_expense_series_field_updates(series_expenses, form, new_end_date):
    """Actualiza o elimina filas según nueva fecha fin. Modifica series_expenses in-place."""
    deleted_count = 0
    for series_expense in series_expenses[:]:
        if new_end_date and series_expense.date > new_end_date:
            db.session.delete(series_expense)
            series_expenses.remove(series_expense)
            deleted_count += 1
        else:
            series_expense.category_id = form.category_id.data
            series_expense.amount = form.amount.data
            series_expense.description = form.description.data
            series_expense.notes = form.notes.data
            series_expense.recurrence_frequency = (
                form.recurrence_frequency.data if form.is_recurring.data else None
            )
            series_expense.recurrence_end_date = new_end_date
    return deleted_count


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

    integration_expense_categories = [
        c
        for c in categories
        if c.name not in (AJUSTES_CATEGORY_NAME, STOCK_MARKET_CATEGORY_NAME)
    ]

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
        integration_expense_categories=integration_expense_categories,
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
    """Editar gasto; series recurrentes: elegir ámbito (serie / futuras / solo esta entrada)."""
    expense = Expense.query.get_or_404(id)

    if expense.user_id != current_user.id:
        flash('No tienes permiso para editar este gasto', 'error')
        return redirect(url_for('expenses.list'))

    needs_scope = _expense_needs_recurrence_scope_choice(expense)
    recurrence_edit_scope = None
    pivot_date_str = None

    if needs_scope and request.method == 'GET':
        scope_from_url = request.args.get('scope')
        if scope_from_url not in RECURRENCE_EDIT_SCOPES:
            return render_template(
                'expenses/choose_recurrence_edit_scope.html',
                expense=expense,
            )
        recurrence_edit_scope = scope_from_url
        pivot_date_str = expense.date.isoformat()

    form = ExpenseForm(obj=expense)

    if request.method == 'POST' and needs_scope:
        recurrence_edit_scope = request.form.get('edit_scope')
        pivot_date_str = request.form.get('pivot_date')

    # Cargar categorías
    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()

    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]

    is_part_of_series = expense.is_recurring and expense.recurrence_group_id

    if form.validate_on_submit():
        old_date = expense.date
        was_not_recurring = not expense.is_recurring
        will_be_recurring = form.is_recurring.data

        if needs_scope:
            if recurrence_edit_scope not in RECURRENCE_EDIT_SCOPES:
                flash('Ámbito de edición no válido.', 'error')
                return redirect(url_for('expenses.edit', id=id))
            pivot = parse_pivot_date(pivot_date_str)
            if not pivot or not _pivot_belongs_to_expense_series(
                current_user.id, expense.recurrence_group_id, pivot
            ):
                flash('No se pudo validar la referencia de la serie.', 'error')
                return redirect(url_for('expenses.list'))

        if was_not_recurring and will_be_recurring:
            if needs_scope:
                flash('Operación no permitida.', 'error')
                return redirect(url_for('expenses.list'))
            temp_expense = Expense(
                user_id=current_user.id,
                category_id=form.category_id.data,
                amount=form.amount.data,
                description=form.description.data,
                date=form.date.data,
                notes=form.notes.data,
                is_recurring=True,
                recurrence_frequency=form.recurrence_frequency.data,
                recurrence_end_date=form.recurrence_end_date.data,
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
            flash(
                f'✅ Gasto convertido a recurrente: {len(expense_instances)} entradas generadas',
                'success',
            )

        elif needs_scope and recurrence_edit_scope == 'entry':
            expense.category_id = form.category_id.data
            expense.amount = form.amount.data
            expense.description = form.description.data
            expense.date = form.date.data
            expense.notes = form.notes.data
            db.session.commit()
            _touch_dashboard_for_expense_dates(
                current_user.id,
                [d for d in (old_date, expense.date) if d],
            )
            flash('✅ Entrada actualizada (resto de la serie sin cambios)', 'success')

        elif needs_scope and recurrence_edit_scope == 'future':
            series_expenses = (
                Expense.query.filter(
                    Expense.user_id == current_user.id,
                    Expense.recurrence_group_id == expense.recurrence_group_id,
                    Expense.date >= pivot,
                )
                .order_by(Expense.date)
                .all()
            )
            series_dates_for_cache = [e.date for e in series_expenses if e.date]
            new_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            deleted_count = _apply_expense_series_field_updates(
                series_expenses, form, new_end_date
            )
            db.session.commit()
            _touch_dashboard_for_expense_dates(current_user.id, series_dates_for_cache)
            if deleted_count > 0:
                flash(
                    f'✅ Entradas futuras actualizadas: {len(series_expenses)} gastos, '
                    f'{deleted_count} eliminados por fecha de fin',
                    'success',
                )
            else:
                flash(
                    f'✅ Entradas desde esta fecha actualizadas ({len(series_expenses)} gastos)',
                    'success',
                )

        elif needs_scope and recurrence_edit_scope == 'series':
            series_expenses = Expense.query.filter_by(
                user_id=current_user.id,
                recurrence_group_id=expense.recurrence_group_id,
            ).all()
            series_dates_for_cache = [e.date for e in series_expenses if e.date]
            new_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            deleted_count = _apply_expense_series_field_updates(
                series_expenses, form, new_end_date
            )
            db.session.commit()
            _touch_dashboard_for_expense_dates(current_user.id, series_dates_for_cache)
            if deleted_count > 0:
                flash(
                    f'✅ Serie actualizada: {len(series_expenses)} gastos, '
                    f'{deleted_count} eliminados por fecha de fin',
                    'success',
                )
            else:
                flash(f'✅ Serie completa actualizada ({len(series_expenses)} gastos)', 'success')

        else:
            expense.category_id = form.category_id.data
            expense.amount = form.amount.data
            expense.description = form.description.data
            expense.date = form.date.data
            expense.notes = form.notes.data
            expense.is_recurring = form.is_recurring.data
            expense.recurrence_frequency = (
                form.recurrence_frequency.data if form.is_recurring.data else None
            )
            expense.recurrence_end_date = (
                form.recurrence_end_date.data if form.is_recurring.data else None
            )

            db.session.commit()
            _touch_dashboard_for_expense_dates(
                current_user.id,
                [d for d in (old_date, expense.date) if d],
            )
            flash('Gasto actualizado', 'success')

        return redirect(url_for('expenses.list'))

    if recurrence_edit_scope == 'series':
        title = 'Editar serie completa (gastos)'
    elif recurrence_edit_scope == 'future':
        title = 'Editar entradas futuras (gastos)'
    elif recurrence_edit_scope == 'entry':
        title = 'Editar solo esta entrada (gasto)'
    elif is_part_of_series:
        title = 'Editar Serie de Gastos'
    else:
        title = 'Editar Gasto'

    lock_recurrence_fields = recurrence_edit_scope == 'entry'

    return render_template(
        'expenses/form.html',
        form=form,
        title=title,
        expense=expense,
        is_part_of_series=bool(is_part_of_series and not needs_scope),
        recurrence_edit_scope=recurrence_edit_scope,
        pivot_date_str=pivot_date_str,
        lock_recurrence_fields=lock_recurrence_fields,
    )


@expenses_bp.route('/<int:id>/terminate-recurrence', methods=['POST'])
@login_required
def terminate_recurrence(id):
    """Elimina entradas futuras de la serie y fija fecha de fin en las restantes."""
    expense = Expense.query.get_or_404(id)

    if expense.user_id != current_user.id:
        flash('No tienes permiso', 'error')
        return redirect(url_for('expenses.list'))

    if not expense.recurrence_group_id or expense.debt_plan_id:
        flash('Esta acción solo aplica a series recurrentes sin plan de deuda.', 'error')
        return redirect(url_for('expenses.list'))

    gid = expense.recurrence_group_id
    pivot = expense.date

    future_rows = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.recurrence_group_id == gid,
        Expense.date > pivot,
    ).all()

    dates_touch = [e.date for e in future_rows if e.date]
    for row in future_rows:
        db.session.delete(row)

    remaining = Expense.query.filter_by(
        user_id=current_user.id,
        recurrence_group_id=gid,
    ).all()
    for r in remaining:
        r.recurrence_end_date = pivot

    db.session.commit()
    dates_touch.extend([r.date for r in remaining if r.date])
    _touch_dashboard_for_expense_dates(current_user.id, dates_touch)
    flash(
        'Contrato terminado: se eliminaron las cuotas futuras de esta serie.',
        'success',
    )
    return redirect(url_for('expenses.list'))


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

