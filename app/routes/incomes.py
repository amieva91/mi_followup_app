"""
Blueprint para gestión de ingresos
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import IncomeCategory, Income
from app.forms import IncomeCategoryForm, IncomeForm
from app.utils.recurrence import create_recurrence_instances
from app.services.category_helpers import filter_editable_categories, is_ajustes_category
from app.services.income_expense_aggregator import (
    get_income_category_summary_with_adjustment,
    get_income_monthly_totals_with_adjustment,
    get_synthetic_income_entries_by_month,
)
from app.services.summary_metrics_service import get_income_summary_metrics
from app.services.dashboard_summary_cache import DashboardSummaryCacheService

incomes_bp = Blueprint('incomes', __name__, url_prefix='/incomes')


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
    
    if not categories:
        flash('Primero debes crear al menos una categoría de ingresos', 'warning')
        return redirect(url_for('incomes.new_category'))
    
    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]
    
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
    """Editar ingreso (si es recurrente, edita toda la serie)"""
    income = Income.query.get_or_404(id)
    
    if income.user_id != current_user.id:
        flash('No tienes permiso para editar este ingreso', 'error')
        return redirect(url_for('incomes.list'))
    
    form = IncomeForm(obj=income)
    
    # Cargar categorías
    categories = IncomeCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(IncomeCategory.name).all()
    
    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]
    
    # Verificar si es parte de una serie recurrente
    is_part_of_series = income.is_recurring and income.recurrence_group_id
    
    if form.validate_on_submit():
        old_date = income.date
        # Detectar si cambió de puntual a recurrente
        was_not_recurring = not income.is_recurring
        will_be_recurring = form.is_recurring.data
        
        if was_not_recurring and will_be_recurring:
            # Cambió de puntual a recurrente: generar nuevas instancias
            temp_income = Income(
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
            
            income_instances = create_recurrence_instances(Income, temp_income, current_user.id)
            db.session.delete(income)
            
            for new_income in income_instances:
                db.session.add(new_income)
            
            db.session.commit()
            _touch_dashboard_for_income_dates(
                current_user.id,
                [old_date] + [i.date for i in income_instances if i.date],
            )
            flash(f'✅ Ingreso convertido a recurrente: {len(income_instances)} entradas generadas', 'success')
        
        elif is_part_of_series:
            # Es parte de una serie: actualizar TODA la serie
            series_incomes = Income.query.filter_by(
                user_id=current_user.id,
                recurrence_group_id=income.recurrence_group_id
            ).all()
            series_dates_for_cache = [i.date for i in series_incomes if i.date]
            
            # Si la fecha de fin cambió a una anterior, eliminar entradas posteriores
            new_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            deleted_count = 0
            
            for series_income in series_incomes[:]:  # Copia para iterar mientras modificamos
                # Si hay nueva fecha de fin y esta entrada es posterior, eliminarla
                if new_end_date and series_income.date > new_end_date:
                    db.session.delete(series_income)
                    series_incomes.remove(series_income)
                    deleted_count += 1
                else:
                    # Actualizar la entrada
                    series_income.category_id = form.category_id.data
                    series_income.amount = form.amount.data
                    series_income.description = form.description.data
                    series_income.notes = form.notes.data
                    series_income.recurrence_frequency = form.recurrence_frequency.data if form.is_recurring.data else None
                    series_income.recurrence_end_date = new_end_date
                    # NO actualizar la fecha, cada entrada mantiene su fecha
            
            db.session.commit()
            _touch_dashboard_for_income_dates(current_user.id, series_dates_for_cache)
            
            if deleted_count > 0:
                flash(f'✅ Serie actualizada: {len(series_incomes)} ingresos actualizados, {deleted_count} eliminados', 'success')
            else:
                flash(f'✅ Serie completa actualizada ({len(series_incomes)} ingresos)', 'success')
        
        else:
            # Actualización normal (ingreso puntual)
            income.category_id = form.category_id.data
            income.amount = form.amount.data
            income.description = form.description.data
            income.date = form.date.data
            income.notes = form.notes.data
            income.is_recurring = form.is_recurring.data
            income.recurrence_frequency = form.recurrence_frequency.data if form.is_recurring.data else None
            income.recurrence_end_date = form.recurrence_end_date.data if form.is_recurring.data else None
            
            db.session.commit()
            _touch_dashboard_for_income_dates(
                current_user.id,
                [d for d in (old_date, income.date) if d],
            )
            flash(f'Ingreso actualizado', 'success')
        
        return redirect(url_for('incomes.list'))
    
    # Agregar información en el título si es parte de una serie
    title = 'Editar Serie de Ingresos' if is_part_of_series else 'Editar Ingreso'
    
    return render_template(
        'incomes/form.html',
        form=form,
        title=title,
        income=income,
        is_part_of_series=is_part_of_series
    )


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

