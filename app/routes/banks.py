"""
Blueprint para gestión de cuentas bancarias
"""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Bank, BankBalance
from app.forms import BankForm
from app.services.bank_service import BankService

banks_bp = Blueprint('banks', __name__, url_prefix='/banks')


@banks_bp.route('/')
@login_required
def dashboard():
    """Dashboard de bancos: lista, saldos del mes, gráfico"""
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month

    # Validar mes
    if month < 1:
        month = 1
    if month > 12:
        month = 12

    banks = BankService.get_banks(current_user.id)
    balances = BankService.get_balances_for_month(current_user.id, year, month)
    total_cash = BankService.get_total_cash_by_month(current_user.id, year, month)
    cash_evolution = BankService.get_cash_evolution(current_user.id, months=12)

    return render_template(
        'banks/dashboard.html',
        banks=banks,
        balances=balances,
        total_cash=total_cash,
        cash_evolution=cash_evolution,
        selected_year=year,
        selected_month=month
    )


@banks_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo banco"""
    form = BankForm()
    if form.validate_on_submit():
        bank = Bank(
            user_id=current_user.id,
            name=form.name.data.strip(),
            icon=form.icon.data or '🏦',
            color=form.color.data or 'blue'
        )
        db.session.add(bank)
        db.session.commit()
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService
        DashboardSummaryCacheService.invalidate(current_user.id)
        flash(f'Banco "{bank.name}" añadido', 'success')
        return redirect(url_for('banks.dashboard'))
    return render_template('banks/bank_form.html', form=form, title='Nuevo banco')


@banks_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Editar banco"""
    bank = Bank.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = BankForm(obj=bank)
    if form.validate_on_submit():
        bank.name = form.name.data.strip()
        bank.icon = form.icon.data or '🏦'
        bank.color = form.color.data or 'blue'
        db.session.commit()
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService
        DashboardSummaryCacheService.invalidate(current_user.id)
        flash(f'Banco "{bank.name}" actualizado', 'success')
        return redirect(url_for('banks.dashboard'))
    return render_template('banks/bank_form.html', form=form, title='Editar banco', bank=bank)


@banks_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Eliminar banco"""
    bank = Bank.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = bank.name
    db.session.delete(bank)
    db.session.commit()
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    DashboardSummaryCacheService.invalidate(current_user.id)
    flash(f'Banco "{name}" eliminado', 'info')
    return redirect(url_for('banks.dashboard'))


@banks_bp.route('/balances', methods=['POST'])
@login_required
def save_balances():
    """Guardar saldos del mes"""
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    if not year or not month or month < 1 or month > 12:
        flash('Mes o año inválido', 'error')
        return redirect(url_for('banks.dashboard'))

    balances = {}
    for key, value in request.form.items():
        if key.startswith('balance_'):
            try:
                bank_id = int(key.replace('balance_', ''))
                balances[bank_id] = value
            except ValueError:
                pass

    BankService.save_balances(current_user.id, year, month, balances)
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    DashboardSummaryCacheService.invalidate(current_user.id)
    flash('Saldos guardados', 'success')
    return redirect(url_for('banks.dashboard', year=year, month=month))
