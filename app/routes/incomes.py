"""
Blueprint para gestión de ingresos
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import IncomeCategory, Income
from app.forms import IncomeCategoryForm, IncomeForm
from app.utils.recurrence import create_recurrence_instances
from app.utils.recurrence_edit_scope import RECURRENCE_EDIT_SCOPES, parse_pivot_date
from app.services.category_helpers import (
    AJUSTES_CATEGORY_NAME,
    STOCK_MARKET_CATEGORY_NAME,
    filter_editable_categories,
    is_ajustes_category,
)
from app.services.income_expense_aggregator import (
    get_income_category_summary_with_adjustment,
    get_income_monthly_totals_with_adjustment,
    get_synthetic_income_entries_by_month,
)
from app.services.summary_metrics_service import get_income_summary_metrics
from app.services.dashboard_summary_cache import DashboardSummaryCacheService

incomes_bp = Blueprint('incomes', __name__, url_prefix='/incomes')


def _income_needs_recurrence_scope_choice(income):
    return bool(income.is_recurring and income.recurrence_group_id)


def _pivot_belongs_to_income_series(user_id, group_id, pivot):
    return (
        Income.query.filter(
            Income.user_id == user_id,
            Income.recurrence_group_id == group_id,
            Income.date == pivot,
        ).first()
        is not None
    )


def _apply_income_series_field_updates(series_incomes, form, new_end_date):
    deleted_count = 0
    for series_income in series_incomes[:]:
        if new_end_date and series_income.date > new_end_date:
            db.session.delete(series_income)
            series_incomes.remove(series_income)
            deleted_count += 1
        else:
            series_income.category_id = form.category_id.data
            series_income.amount = form.amount.data
            series_income.description = form.description.data
            series_income.notes = form.notes.data
            series_income.recurrence_frequency = (
                form.recurrence_frequency.data if form.is_recurring.data else None
            )
            series_income.recurrence_end_date = new_end_date
    return deleted_count


def _touch_dashboard_for_income_dates(user_id, dates):
    if dates:
        DashboardSummaryCacheService.touch_for_dates(user_id, dates=dates)


# ==================== CATEGORÍAS ====================

@incomes_bp.route('/categories')
@login_required
def categories():
    """Listar categorías de ingresos (agrupadas jerárquicamente)"""
    parent_categories = IncomeCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None
    ).order_by(IncomeCategory.name).all()
    
    categories = []
    for parent in parent_categories:
        categories.append(parent)
        subcategories = IncomeCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=parent.id
        ).order_by(IncomeCategory.name).all()
        categories.extend(subcategories)
    
    return render_template(
        'incomes/categories.html',
        categories=categories
    )


@incomes_bp.route('/categories/quick-create', methods=['POST'])
@login_required
def quick_create_category():
    """API: crear categoría de ingreso desde modal, devuelve JSON."""
    name = request.form.get('name') or (request.json.get('name') if request.is_json else None)
    icon = request.form.get('icon', '💵') or '💵'
    if not name or not name.strip():
        return jsonify({'error': 'El nombre es requerido'}), 400
    parent_id = request.form.get('parent_id', type=int) or (request.json.get('parent_id') if request.is_json else 0) or 0
    cat = IncomeCategory(
        name=name.strip(),
        icon=icon or '💵',
        color='green',
        user_id=current_user.id,
        parent_id=parent_id if parent_id else None
    )
    db.session.add(cat)
    db.session.commit()
    label = f"{cat.icon} {cat.full_name}"
    return jsonify({'id': cat.id, 'name': cat.name, 'icon': cat.icon, 'full_name': cat.full_name, 'label': label})


@incomes_bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
def new_category():
    """Crear nueva categoría"""
    form = IncomeCategoryForm()
    form.parent_id.choices = [(0, '-- Sin categoría padre --')] + [
        (c.id, c.name) for c in IncomeCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=None
        ).order_by(IncomeCategory.name).all()
    ]
    
    if form.validate_on_submit():
        if form.name.data.strip() == 'Ajustes':
            flash('El nombre "Ajustes" está reservado para el sistema', 'warning')
            return redirect(url_for('incomes.new_category'))
        category = IncomeCategory(
            name=form.name.data,
            icon=form.icon.data or '💵',
            color=form.color.data,
            user_id=current_user.id,
            parent_id=form.parent_id.data if form.parent_id.data != 0 else None
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
    
    if is_ajustes_category(category):
        flash('La categoría Ajustes está reservada para el sistema y no puede editarse', 'warning')
        return redirect(url_for('incomes.categories'))
    if category.user_id != current_user.id:
        flash('No tienes permiso para editar esta categoría', 'error')
        return redirect(url_for('incomes.categories'))
    
    form = IncomeCategoryForm(obj=category)
    form.parent_id.choices = [(0, '-- Sin categoría padre --')] + [
        (c.id, c.name) for c in IncomeCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=None
        ).filter(IncomeCategory.id != id).order_by(IncomeCategory.name).all()
    ]
    form.parent_id.data = category.parent_id or 0
    
    if form.validate_on_submit():
        if form.name.data.strip() == 'Ajustes':
            flash('El nombre "Ajustes" está reservado para el sistema', 'warning')
            return redirect(url_for('incomes.categories'))
        category.name = form.name.data
        category.icon = form.icon.data or '💵'
        category.color = form.color.data
        category.parent_id = form.parent_id.data if form.parent_id.data != 0 else None
        
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
    
    if is_ajustes_category(category):
        flash('La categoría Ajustes está reservada para el sistema y no puede eliminarse', 'warning')
        return redirect(url_for('incomes.categories'))
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

    integration_income_categories = [
        c
        for c in categories
        if c.name not in (AJUSTES_CATEGORY_NAME, STOCK_MARKET_CATEGORY_NAME)
    ]

    # Resumen por categoría (12 meses) incluyendo ajuste de reconciliación
    category_summary = get_income_category_summary_with_adjustment(current_user.id, months=12)
    # Totales mensuales (12 meses) para gráfico de barras incluyendo ajuste
    monthly_totals = get_income_monthly_totals_with_adjustment(current_user.id, months=12)
    # Métricas de resumen (Fase 6)
    summary_metrics = get_income_summary_metrics(current_user.id, months=12)
    # Entradas sintéticas por mes (Ajustes y Stock Market) - todo el histórico
    synthetic_entries = get_synthetic_income_entries_by_month(current_user.id, months=None)
    
    # Calcular meses con entradas sintéticas pero SIN ingresos reales
    # para mostrarlos como filas independientes en la tabla
    orphan_synthetic_entries = []
    if synthetic_entries:
        # Obtener todos los meses únicos que tienen ingresos reales
        months_with_real_incomes = set()
        all_incomes_query = Income.query.filter_by(user_id=current_user.id).with_entities(
            db.func.extract('year', Income.date).label('year'),
            db.func.extract('month', Income.date).label('month')
        ).distinct().all()
        for row in all_incomes_query:
            months_with_real_incomes.add((int(row.year), int(row.month)))
        
        # Identificar meses sintéticos huérfanos (sin ingresos reales)
        for (year, month), data in sorted(synthetic_entries.items(), reverse=True):
            if (year, month) not in months_with_real_incomes:
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
        'incomes/list.html',
        incomes=incomes,
        categories=categories,
        integration_income_categories=integration_income_categories,
        selected_category=category_id,
        category_summary=category_summary,
        monthly_totals=monthly_totals,
        summary_metrics=summary_metrics,
        synthetic_entries=synthetic_entries,
        orphan_synthetic_entries=orphan_synthetic_entries
    )


@incomes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo ingreso"""
    form = IncomeForm()
    
    # Cargar categorías (excluir Ajustes, reservada para el sistema)
    categories = filter_editable_categories(
        IncomeCategory.query.filter_by(user_id=current_user.id).order_by(IncomeCategory.name).all()
    )
    form.category_id.choices = (
        [(c.id, f"{c.icon} {c.full_name}") for c in categories] if categories else []
    )
    if not categories:
        flash(
            'Crea tu primera categoría con el botón + junto a «Categoría», o en Ingresos → Categorías.',
            'info',
        )
    
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
        _touch_dashboard_for_income_dates(
            current_user.id,
            [i.date for i in income_instances if i.date],
        )
        
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
    """Editar ingreso; series recurrentes: elegir ámbito (serie / futuras / solo esta entrada)."""
    income = Income.query.get_or_404(id)

    if income.user_id != current_user.id:
        flash('No tienes permiso para editar este ingreso', 'error')
        return redirect(url_for('incomes.list'))

    needs_scope = _income_needs_recurrence_scope_choice(income)
    recurrence_edit_scope = None
    pivot_date_str = None

    if needs_scope and request.method == 'GET':
        scope_from_url = request.args.get('scope')
        if scope_from_url not in RECURRENCE_EDIT_SCOPES:
            flash(
                'Elige el ámbito de edición con el botón ✏️ en la lista: serie completa, '
                'solo futuras o solo esta entrada.',
                'info',
            )
            return redirect(url_for('incomes.list'))
        recurrence_edit_scope = scope_from_url
        pivot_date_str = income.date.isoformat()

    form = IncomeForm(obj=income)

    if request.method == 'POST' and needs_scope:
        recurrence_edit_scope = request.form.get('edit_scope')
        pivot_date_str = request.form.get('pivot_date')

    categories = IncomeCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(IncomeCategory.name).all()

    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]

    is_part_of_series = income.is_recurring and income.recurrence_group_id

    if form.validate_on_submit():
        old_date = income.date
        was_not_recurring = not income.is_recurring
        will_be_recurring = form.is_recurring.data

        if needs_scope:
            if recurrence_edit_scope not in RECURRENCE_EDIT_SCOPES:
                flash('Ámbito de edición no válido.', 'error')
                return redirect(url_for('incomes.edit', id=id))
            pivot = parse_pivot_date(pivot_date_str)
            if not pivot or not _pivot_belongs_to_income_series(
                current_user.id, income.recurrence_group_id, pivot
            ):
                flash('No se pudo validar la referencia de la serie.', 'error')
                return redirect(url_for('incomes.list'))

        if was_not_recurring and will_be_recurring:
            if needs_scope:
                flash('Operación no permitida.', 'error')
                return redirect(url_for('incomes.list'))
            temp_income = Income(
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

            income_instances = create_recurrence_instances(Income, temp_income, current_user.id)
            db.session.delete(income)

            for new_income in income_instances:
                db.session.add(new_income)

            db.session.commit()
            _touch_dashboard_for_income_dates(
                current_user.id,
                [old_date] + [i.date for i in income_instances if i.date],
            )
            flash(
                f'✅ Ingreso convertido a recurrente: {len(income_instances)} entradas generadas',
                'success',
            )

        elif needs_scope and recurrence_edit_scope == 'entry':
            income.category_id = form.category_id.data
            income.amount = form.amount.data
            income.description = form.description.data
            income.date = form.date.data
            income.notes = form.notes.data
            db.session.commit()
            _touch_dashboard_for_income_dates(
                current_user.id,
                [d for d in (old_date, income.date) if d],
            )
            flash('✅ Entrada actualizada (resto de la serie sin cambios)', 'success')

        elif needs_scope and recurrence_edit_scope == 'future':
            series_incomes = (
                Income.query.filter(
                    Income.user_id == current_user.id,
                    Income.recurrence_group_id == income.recurrence_group_id,
                    Income.date >= pivot,
                )
                .order_by(Income.date)
                .all()
            )
            series_dates_for_cache = [i.date for i in series_incomes if i.date]
            new_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            deleted_count = _apply_income_series_field_updates(
                series_incomes, form, new_end_date
            )
            db.session.commit()
            _touch_dashboard_for_income_dates(current_user.id, series_dates_for_cache)
            if deleted_count > 0:
                flash(
                    f'✅ Entradas futuras actualizadas: {len(series_incomes)} ingresos, '
                    f'{deleted_count} eliminados por fecha de fin',
                    'success',
                )
            else:
                flash(
                    f'✅ Entradas desde esta fecha actualizadas ({len(series_incomes)} ingresos)',
                    'success',
                )

        elif needs_scope and recurrence_edit_scope == 'series':
            series_incomes = Income.query.filter_by(
                user_id=current_user.id,
                recurrence_group_id=income.recurrence_group_id,
            ).all()
            series_dates_for_cache = [i.date for i in series_incomes if i.date]
            new_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            deleted_count = _apply_income_series_field_updates(
                series_incomes, form, new_end_date
            )
            db.session.commit()
            _touch_dashboard_for_income_dates(current_user.id, series_dates_for_cache)
            if deleted_count > 0:
                flash(
                    f'✅ Serie actualizada: {len(series_incomes)} ingresos, '
                    f'{deleted_count} eliminados por fecha de fin',
                    'success',
                )
            else:
                flash(f'✅ Serie completa actualizada ({len(series_incomes)} ingresos)', 'success')

        else:
            income.category_id = form.category_id.data
            income.amount = form.amount.data
            income.description = form.description.data
            income.date = form.date.data
            income.notes = form.notes.data
            income.is_recurring = form.is_recurring.data
            income.recurrence_frequency = (
                form.recurrence_frequency.data if form.is_recurring.data else None
            )
            income.recurrence_end_date = (
                form.recurrence_end_date.data if form.is_recurring.data else None
            )

            db.session.commit()
            _touch_dashboard_for_income_dates(
                current_user.id,
                [d for d in (old_date, income.date) if d],
            )
            flash('Ingreso actualizado', 'success')

        return redirect(url_for('incomes.list'))

    if recurrence_edit_scope == 'series':
        title = 'Editar serie completa (ingresos)'
    elif recurrence_edit_scope == 'future':
        title = 'Editar entradas futuras (ingresos)'
    elif recurrence_edit_scope == 'entry':
        title = 'Editar solo esta entrada (ingreso)'
    elif is_part_of_series:
        title = 'Editar Serie de Ingresos'
    else:
        title = 'Editar Ingreso'

    lock_recurrence_fields = recurrence_edit_scope == 'entry'

    return render_template(
        'incomes/form.html',
        form=form,
        title=title,
        income=income,
        is_part_of_series=bool(is_part_of_series and not needs_scope),
        recurrence_edit_scope=recurrence_edit_scope,
        pivot_date_str=pivot_date_str,
        lock_recurrence_fields=lock_recurrence_fields,
    )


@incomes_bp.route('/<int:id>/terminate-recurrence', methods=['POST'])
@login_required
def terminate_recurrence(id):
    """Elimina ingresos futuros de la serie y fija fecha de fin en las restantes."""
    income = Income.query.get_or_404(id)

    if income.user_id != current_user.id:
        flash('No tienes permiso', 'error')
        return redirect(url_for('incomes.list'))

    if not income.recurrence_group_id:
        flash('Esta acción solo aplica a series recurrentes.', 'error')
        return redirect(url_for('incomes.list'))

    gid = income.recurrence_group_id
    pivot = income.date

    future_rows = Income.query.filter(
        Income.user_id == current_user.id,
        Income.recurrence_group_id == gid,
        Income.date > pivot,
    ).all()

    dates_touch = [i.date for i in future_rows if i.date]
    for row in future_rows:
        db.session.delete(row)

    remaining = Income.query.filter_by(
        user_id=current_user.id,
        recurrence_group_id=gid,
    ).all()
    for r in remaining:
        r.recurrence_end_date = pivot

    db.session.commit()
    dates_touch.extend([r.date for r in remaining if r.date])
    _touch_dashboard_for_income_dates(current_user.id, dates_touch)
    flash(
        'Contrato terminado: se eliminaron las cuotas futuras de esta serie.',
        'success',
    )
    return redirect(url_for('incomes.list'))


@incomes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Eliminar ingreso"""
    income = Income.query.get_or_404(id)
    
    if income.user_id != current_user.id:
        flash('No tienes permiso para eliminar este ingreso', 'error')
        return redirect(url_for('incomes.list'))
    
    # Verificar si es parte de una serie recurrente
    delete_series = request.form.get('delete_series') == 'true'
    
    if income.is_recurring and income.recurrence_group_id and delete_series:
        # Eliminar toda la serie
        series_dates = [
            i.date
            for i in Income.query.filter_by(
                user_id=current_user.id,
                recurrence_group_id=income.recurrence_group_id,
            ).all()
            if i.date
        ]
        count = Income.query.filter_by(
            user_id=current_user.id,
            recurrence_group_id=income.recurrence_group_id
        ).delete()
        
        db.session.commit()
        _touch_dashboard_for_income_dates(current_user.id, series_dates)
        flash(f'✅ Serie completa eliminada ({count} ingresos)', 'info')
    else:
        # Eliminar solo esta entrada
        del_date = income.date
        db.session.delete(income)
        db.session.commit()
        _touch_dashboard_for_income_dates(current_user.id, [del_date] if del_date else [])
        flash('Ingreso eliminado', 'info')
    
    return redirect(url_for('incomes.list'))

