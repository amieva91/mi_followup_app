"""
Rutas para el módulo Cryptomonedas
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import BrokerAccount, Asset, Transaction
from app.forms.portfolio.account_forms import get_brokers_for_account_modal
from app.services.crypto_metrics import compute_crypto_metrics

crypto_bp = Blueprint('crypto', __name__, url_prefix='/crypto')


@crypto_bp.route('/')
@login_required
def dashboard():
    """Dashboard de cryptomonedas: fiat, cuasi-fiat, posiciones, rentabilidad"""
    metrics = compute_crypto_metrics(current_user.id)
    return render_template('crypto/dashboard.html', metrics=metrics)


@crypto_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Nueva compra o venta de criptomoneda (manual)"""
    from app.forms.crypto_forms import CryptoTransactionForm

    form = CryptoTransactionForm()
    accounts = BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    form.account_id.choices = [
        (acc.id, f'{acc.broker.name} - {acc.account_name}')
        for acc in accounts
    ]
    if not form.account_id.choices:
        flash('No tienes ninguna cuenta. Crea una en Carga de Datos → Cuentas.', 'warning')
        return redirect(url_for('portfolio.accounts_list'))

    if form.validate_on_submit():
        account_id = int(form.account_id.data)
        symbol = form.symbol.data.strip().upper()
        currency = form.currency.data or 'EUR'

        # Buscar o crear el asset
        asset = Asset.query.filter_by(
            symbol=symbol,
            asset_type='Crypto',
            currency=currency
        ).first()
        if not asset:
            name = f"{symbol} (Crypto)"
            yahoo_suffix = f'-{currency}'  # BTC-EUR, ETH-USD
            asset = Asset(
                symbol=symbol,
                asset_type='Crypto',
                currency=currency,
                name=name,
                yahoo_suffix=yahoo_suffix,
            )
            db.session.add(asset)
            db.session.flush()

        qty = form.quantity.data
        price = form.price.data
        total = qty * price
        amount = -total if form.transaction_type.data == 'BUY' else total
        commission = form.commission.data or 0

        txn = Transaction(
            user_id=current_user.id,
            account_id=account_id,
            asset_id=asset.id,
            transaction_type=form.transaction_type.data,
            transaction_date=datetime.combine(form.transaction_date.data, datetime.min.time()),
            settlement_date=form.transaction_date.data,
            quantity=qty,
            price=price,
            amount=amount,
            currency=currency,
            commission=commission,
            fees=0,
            tax=0,
            notes=form.notes.data,
            source='MANUAL',
        )
        db.session.add(txn)
        db.session.flush()

        from app.services.portfolio_holding_service import recalculate_holdings
        from app.services.metrics.cache import MetricsCacheService

        recalculate_holdings(current_user.id, account_id)
        db.session.commit()
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService
        MetricsCacheService.invalidate(current_user.id)
        DashboardSummaryCacheService.invalidate(current_user.id)

        flash(f"✅ {form.transaction_type.data} registrado: {qty} {symbol}", 'success')
        return redirect(url_for('crypto.dashboard'))

    return render_template(
        'crypto/transaction_form.html',
        form=form,
        brokers_for_account_modal=get_brokers_for_account_modal(),
    )


@crypto_bp.route('/import')
@login_required
def import_csv():
    """Redirige a la subida de CSV de portfolio (soporta Revolut X)"""
    return redirect(url_for('portfolio.import_csv'))
