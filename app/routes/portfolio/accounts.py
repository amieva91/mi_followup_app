"""
Rutas de cuentas de broker (CRUD)
"""
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app import db
from app.models import Broker, BrokerAccount, PortfolioHolding, Transaction
from app.forms import BrokerAccountForm


@portfolio_bp.route('/accounts')
@login_required
def accounts_list():
    """Lista de cuentas del usuario"""
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    return render_template('portfolio/accounts.html', accounts=accounts)


@portfolio_bp.route('/accounts/new', methods=['GET', 'POST'])
@login_required
def account_new():
    """Crear nueva cuenta de broker"""
    form = BrokerAccountForm(add_new_broker_option=True)

    if form.validate_on_submit():
        broker_id = form.broker_id.data
        if not broker_id and form.broker_name_new.data:
            name = form.broker_name_new.data.strip()
            broker = Broker.query.filter(db.func.lower(Broker.name) == name.lower()).first()
            if not broker:
                broker = Broker(name=name, full_name=name, is_active=True)
                db.session.add(broker)
                db.session.flush()
            broker_id = broker.id

        account = BrokerAccount(
            user_id=current_user.id,
            broker_id=broker_id,
            account_name=form.account_name.data,
            base_currency=form.base_currency.data
        )
        db.session.add(account)
        db.session.commit()
        flash(f'✅ Cuenta "{account.account_name}" creada correctamente', 'success')
        return redirect(url_for('portfolio.accounts_list'))

    return render_template('portfolio/account_form.html', form=form, title='Nueva Cuenta')


@portfolio_bp.route('/accounts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def account_edit(id):
    """Editar cuenta de broker"""
    account = BrokerAccount.query.get_or_404(id)

    if account.user_id != current_user.id:
        flash('No tienes permiso para editar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))

    form = BrokerAccountForm(obj=account)

    if form.validate_on_submit():
        account.broker_id = form.broker_id.data
        account.account_name = form.account_name.data
        account.base_currency = form.base_currency.data
        db.session.commit()
        flash('Cuenta actualizada correctamente', 'success')
        return redirect(url_for('portfolio.accounts_list'))

    return render_template('portfolio/account_form.html', form=form, title='Editar Cuenta', account=account)


@portfolio_bp.route('/accounts/<int:id>/clear', methods=['POST'])
@login_required
def account_clear(id):
    """Vaciar cuenta de broker"""
    account = BrokerAccount.query.get_or_404(id)

    if account.user_id != current_user.id:
        flash('❌ No tienes permiso para modificar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))

    from app.models.metrics import PortfolioMetrics
    from app.models.transaction import CashFlow

    num_holdings = PortfolioHolding.query.filter_by(account_id=id).count()
    num_transactions = Transaction.query.filter_by(account_id=id).count()
    account_name = account.account_name

    PortfolioMetrics.query.filter_by(account_id=id).delete()
    CashFlow.query.filter_by(account_id=id).delete()
    Transaction.query.filter_by(account_id=id).delete()
    PortfolioHolding.query.filter_by(account_id=id).delete()

    account.current_cash = 0.0
    account.margin_used = 0.0
    db.session.commit()

    flash(f'🧹 Cuenta "{account_name}" vaciada correctamente. Se eliminaron {num_transactions} transacciones y {num_holdings} posiciones.', 'success')
    return redirect(url_for('portfolio.accounts_list'))


@portfolio_bp.route('/accounts/<int:id>/delete', methods=['POST'])
@login_required
def account_delete(id):
    """Eliminar cuenta de broker"""
    account = BrokerAccount.query.get_or_404(id)

    if account.user_id != current_user.id:
        flash('No tienes permiso para eliminar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))

    from app.models.metrics import PortfolioMetrics
    from app.models.transaction import CashFlow

    num_holdings = PortfolioHolding.query.filter_by(account_id=id).count()
    num_transactions = Transaction.query.filter_by(account_id=id).count()
    account_name = account.account_name

    PortfolioMetrics.query.filter_by(account_id=id).delete()
    CashFlow.query.filter_by(account_id=id).delete()
    Transaction.query.filter_by(account_id=id).delete()
    PortfolioHolding.query.filter_by(account_id=id).delete()
    db.session.delete(account)
    db.session.commit()

    from app.services.metrics.cache import MetricsCacheService
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    MetricsCacheService.invalidate(current_user.id)
    DashboardSummaryCacheService.invalidate(current_user.id)

    flash(f'🗑️ Cuenta "{account_name}" eliminada permanentemente.', 'success')
    return redirect(url_for('portfolio.accounts_list'))
