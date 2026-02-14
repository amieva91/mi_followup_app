"""
Rutas para el módulo Metales (metales preciosos - Commodity)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.models import Broker, BrokerAccount, Asset, Transaction, PortfolioHolding
from app.services.metales_metrics import compute_metales_metrics, get_metales_holdings
from app.services.currency_service import convert_to_eur

# 1 oz troy = 31.1035 g
OZ_TROY_TO_G = 31.1035

metales_bp = Blueprint('metales', __name__, url_prefix='/metales')


@metales_bp.route('/')
@login_required
def dashboard():
    """Dashboard de metales preciosos"""
    metrics = compute_metales_metrics(current_user.id)
    return render_template('metales/dashboard.html', metrics=metrics)


def _get_or_create_commodities_account():
    """Obtiene o crea la cuenta Commodities del usuario"""
    broker = Broker.query.filter(Broker.name.ilike('%commodit%')).first()
    if not broker:
        return None
    account = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        broker_id=broker.id,
        is_active=True
    ).first()
    if not account:
        account = BrokerAccount(
            user_id=current_user.id,
            broker_id=broker.id,
            account_name='Commodities',
            base_currency='EUR',
        )
        db.session.add(account)
        db.session.flush()
    return account


@metales_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Nueva compra o venta de metal"""
    from app.forms.metales_forms import MetalTransactionForm

    # Assets de metales disponibles
    metals = Asset.query.filter_by(asset_type='Commodity').order_by(Asset.symbol).all()
    if not metals:
        flash('No hay metales configurados. Ejecuta el seed: docs/scripts/seed_metales.py', 'warning')
        return redirect(url_for('metales.dashboard'))

    form = MetalTransactionForm()
    form.metal_id.choices = [(m.id, f"{m.symbol} - {m.name}") for m in metals]

    if form.validate_on_submit():
        account = _get_or_create_commodities_account()
        if not account:
            flash('Error: No existe el broker Commodities. Ejecuta el seed.', 'error')
            return redirect(url_for('metales.dashboard'))

        metal = Asset.query.get(form.metal_id.data)
        if not metal or metal.asset_type != 'Commodity':
            flash('Metal no válido', 'error')
            return redirect(url_for('metales.transaction_new'))

        # Convertir a gramos si el usuario introdujo oz
        qty_g = form.quantity_grams.data
        if form.unit.data == 'oz':
            qty_g = form.quantity_grams.data * OZ_TROY_TO_G

        total_amount = form.total_amount.data
        price_per_unit = total_amount / qty_g if qty_g > 0 else 0
        amount = -total_amount if form.transaction_type.data == 'BUY' else total_amount

        txn = Transaction(
            user_id=current_user.id,
            account_id=account.id,
            asset_id=metal.id,
            transaction_type=form.transaction_type.data,
            transaction_date=datetime.combine(form.transaction_date.data, datetime.min.time()),
            quantity=qty_g,
            price=price_per_unit,
            amount=amount,
            currency='EUR',
            description=f"{'Compra' if form.transaction_type.data == 'BUY' else 'Venta'} {qty_g:.2f} g {metal.name}",
            source='MANUAL',
        )
        db.session.add(txn)
        db.session.flush()

        from app.services.portfolio_holding_service import recalculate_holdings
        from app.services.metrics.cache import MetricsCacheService

        recalculate_holdings(current_user.id, account.id)
        db.session.commit()
        MetricsCacheService.invalidate(current_user.id)

        flash(f"✅ {'Compra' if form.transaction_type.data == 'BUY' else 'Venta'} registrada: {qty_g:.2f} g {metal.name}", 'success')
        return redirect(url_for('metales.dashboard'))

    return render_template('metales/transaction_form.html', form=form, metals=metals)
