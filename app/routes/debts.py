"""
Blueprint para gestión de deudas (pagos a plazos)
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import DebtPlan, Expense, ExpenseCategory
from app.forms import DebtPlanForm, DebtPlanEditForm, DebtRestructureForm
from app.services.debt_service import DebtService

debts_bp = Blueprint('debts', __name__, url_prefix='/debts')


@debts_bp.route('/')
@login_required
def dashboard():
    """Dashboard de deudas: gráfico, resumen, límite"""
    schedule_data = DebtService.get_monthly_debt_schedule(current_user.id, months_back=6)
    total_debt = DebtService.get_total_debt_remaining(current_user.id)
    plans = DebtService.get_active_plans(current_user.id)
    inactive_plans = DebtService.get_inactive_plans(current_user.id)
    limit_info = DebtService.get_debt_limit_info(current_user)

    return render_template(
        'debts/dashboard.html',
        schedule_data=schedule_data,
        total_debt=total_debt,
        plans=plans,
        inactive_plans=inactive_plans,
        limit_info=limit_info,
        get_months_paid=DebtService.get_months_paid
    )


@debts_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo plan de deuda"""
    form = DebtPlanForm()

    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()

    if not categories:
        flash('Primero debes crear al menos una categoría de gastos', 'warning')
        return redirect(url_for('expenses.new_category'))

    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]

    if form.validate_on_submit():
        plan = DebtService.create_debt_plan(
            user_id=current_user.id,
            name=form.name.data,
            total_amount=form.total_amount.data,
            months=form.months.data,
            start_date=form.start_date.data,
            category_id=form.category_id.data,
            notes=form.notes.data
        )
        if plan:
            flash(
                f'✅ Plan de deuda creado: {plan.name} - '
                f'€{plan.monthly_payment:.2f}/mes durante {plan.months} meses',
                'success'
            )
            next_page = request.args.get('next') or request.form.get('next')
            if next_page == 'expenses':
                return redirect(url_for('expenses.list'))
            return redirect(url_for('debts.dashboard'))
        flash('Error al crear el plan de deuda', 'error')

    next_page = request.args.get('next')
    return render_template('debts/form.html', form=form, title='Nueva deuda', next_page=next_page)


@debts_bp.route('/limit', methods=['POST'])
@login_required
def update_limit():
    """Actualizar límite de endeudamiento"""
    try:
        val = float(request.form.get('debt_limit_percent', 35))
        if 5 <= val <= 100:
            current_user.debt_limit_percent = val
            db.session.commit()
            flash(f'Límite de endeudamiento actualizado a {val}%', 'success')
        else:
            flash('El porcentaje debe estar entre 5 y 100', 'error')
    except (ValueError, TypeError):
        flash('Valor inválido', 'error')
    return redirect(url_for('debts.dashboard'))


@debts_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Editar plan de deuda (todos los campos, actualizando cuotas en Gastos)"""
    from datetime import date
    plan = DebtPlan.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = DebtPlanEditForm()

    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id
    ).order_by(ExpenseCategory.name).all()
    form.category_id.choices = [(c.id, f"{c.icon} {c.full_name}") for c in categories]

    if form.validate_on_submit():
        months_paid = Expense.query.filter(
            Expense.debt_plan_id == plan.id,
            Expense.date <= date.today()
        ).count()
        if form.months.data < months_paid:
            flash(f'Los meses no pueden ser menos que las cuotas ya pagadas ({months_paid})', 'error')
        else:
            ok = DebtService.update_debt_plan(
                plan_id=plan.id,
                user_id=current_user.id,
                name=form.name.data,
                total_amount=form.total_amount.data,
                months=form.months.data,
                start_date=form.start_date.data,
                category_id=form.category_id.data,
                notes=form.notes.data
            )
            if ok:
                flash('Plan de deuda actualizado. Las cuotas en Gastos se han sincronizado.', 'success')
            else:
                flash('Error al actualizar el plan', 'error')
            next_page = request.args.get('next') or request.form.get('next')
            if next_page == 'expenses':
                return redirect(url_for('expenses.list'))
            return redirect(url_for('debts.dashboard'))

    if request.method == 'GET':
        form.name.data = plan.name
        form.total_amount.data = plan.total_amount
        form.months.data = plan.months
        form.start_date.data = plan.start_date
        form.category_id.data = plan.category_id
        form.notes.data = plan.notes or ''

    next_page = request.args.get('next')
    return render_template(
        'debts/edit.html',
        form=form,
        plan=plan,
        title='Editar plan de deuda',
        next_page=next_page
    )


@debts_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel(id):
    """Cancelar plan: eliminar todo o solo cuotas a partir de una fecha"""
    delete_future_only = request.form.get('delete_future_only') == 'true'
    cutoff_date = None
    if delete_future_only:
        # Desde expenses: usar fecha del gasto seleccionado (más fiable)
        from_expense_id = request.form.get('from_expense_id', type=int)
        if from_expense_id:
            exp = Expense.query.filter_by(id=from_expense_id, user_id=current_user.id, debt_plan_id=id).first()
            if exp:
                cutoff_date = exp.date
        if cutoff_date is None:
            raw = request.form.get('cutoff_date')
            if raw:
                try:
                    cutoff_date = datetime.strptime(str(raw)[:10], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
    count = DebtService.cancel_plan(id, current_user.id, delete_future_only=delete_future_only, cutoff_date=cutoff_date)
    if delete_future_only:
        flash(f'Plan cancelado. Se eliminaron {count} cuotas futuras.', 'info')
    else:
        flash('Plan de deuda eliminado completamente.', 'info')
    next_url = request.form.get('next')
    if next_url == 'expenses':
        return redirect(url_for('expenses.list'))
    return redirect(url_for('debts.dashboard'))


@debts_bp.route('/<int:id>/restructure', methods=['GET', 'POST'])
@login_required
def restructure(id):
    """Reestructurar plan: cambiar cuota mensual y recalcular meses restantes"""
    plan = DebtPlan.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if plan.status != 'ACTIVE':
        flash('Solo se pueden reestructurar planes activos', 'error')
        return redirect(url_for('debts.dashboard'))

    from datetime import date
    future_expenses = Expense.query.filter(
        Expense.debt_plan_id == plan.id,
        Expense.date > date.today()
    ).all()
    remaining_amount = sum(exp.amount for exp in future_expenses)
    remaining_months = len(future_expenses)

    if not future_expenses:
        flash('No hay cuotas futuras que reestructurar', 'info')
        return redirect(url_for('debts.dashboard'))

    form = DebtRestructureForm()
    if form.validate_on_submit():
        if form.restructure_mode.data == 'by_amount':
            new_months, new_payment, ok = DebtService.restructure_plan(
                id, current_user.id, new_monthly_payment=form.new_monthly_payment.data
            )
        else:
            new_months, new_payment, ok = DebtService.restructure_plan(
                id, current_user.id, new_months=form.new_months.data
            )
        if ok:
            flash(f'Plan reestructurado: nueva cuota de €{new_payment:.2f} en {new_months} meses', 'success')
        else:
            flash('Error al reestructurar el plan', 'error')
        return redirect(url_for('debts.dashboard'))

    form.restructure_mode.data = 'by_amount'
    form.new_monthly_payment.data = plan.monthly_payment
    form.new_months.data = remaining_months

    return render_template(
        'debts/restructure.html',
        form=form,
        plan=plan,
        remaining_amount=remaining_amount,
        remaining_months=remaining_months,
        title='Reestructurar plan de deuda'
    )


@debts_bp.route('/<int:id>/pay-off', methods=['POST'])
@login_required
def pay_off(id):
    """Marcar plan como pagado (elimina cuotas futuras)"""
    count = DebtService.mark_as_paid_off(id, current_user.id)
    flash(f'Plan marcado como pagado. Se eliminaron {count} cuotas futuras.', 'success')
    return redirect(url_for('debts.dashboard'))
