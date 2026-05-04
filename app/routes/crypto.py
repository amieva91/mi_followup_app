"""
Rutas para el módulo Cryptomonedas
"""
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
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
        is_edit=False,
    )


@crypto_bp.route('/api/movimientos')
@login_required
def api_movimientos():
    """
    JSON: transacciones BUY/SELL de un crypto en una cuenta (modal en dashboard).
    """
    account_id = request.args.get('account_id', type=int)
    asset_id = request.args.get('asset_id', type=int)
    if not account_id or not asset_id:
        return jsonify({'ok': False, 'error': 'Indica account_id y asset_id.'}), 400

    acc = BrokerAccount.query.filter_by(
        id=account_id, user_id=current_user.id, is_active=True
    ).first()
    if not acc:
        return jsonify({'ok': False, 'error': 'Cuenta no válida.'}), 404

    asset = db.session.get(Asset, asset_id)
    if not asset or asset.asset_type != 'Crypto':
        return jsonify({'ok': False, 'error': 'Activo no válido.'}), 404

    txns = (
        Transaction.query.filter_by(
            user_id=current_user.id, account_id=account_id, asset_id=asset_id
        )
        .filter(Transaction.transaction_type.in_(('BUY', 'SELL')))
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .all()
    )

    account_label = (
        f'{acc.broker.name} — {acc.account_name}' if acc.broker else acc.account_name
    )
    rows = []
    for t in txns:
        sym = t.asset.symbol if t.asset else ''
        rows.append(
            {
                'id': t.id,
                'date': t.transaction_date.strftime('%d/%m/%Y %H:%M')
                if t.transaction_date
                else '',
                'type': t.transaction_type,
                'symbol': sym,
                'quantity': t.quantity,
                'price': t.price,
                'amount': t.amount,
                'currency': t.currency or 'EUR',
                'commission': float(t.commission or 0),
                'edit_url': url_for('crypto.transaction_edit', id=t.id),
            }
        )

    return jsonify(
        {
            'ok': True,
            'account_label': account_label,
            'asset_name': asset.name or asset.symbol,
            'transactions': rows,
        }
    )


@crypto_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def transaction_edit(id):
    """Editar operación de crypto (mismo formulario que /nueva)."""
    from app.forms.crypto_forms import CryptoTransactionForm
    from app.services.importer_v2 import CSVImporterV2
    from app.services.cache_rebuild_state_service import CacheRebuildStateService
    from app.services.metrics.cache import MetricsCacheService
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService

    transaction = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if transaction.transaction_type not in ('BUY', 'SELL') or not transaction.asset_id:
        flash('Esta operación no se puede editar desde el módulo de crypto.', 'warning')
        return redirect(url_for('crypto.dashboard'))

    a_row = db.session.get(Asset, transaction.asset_id)
    if not a_row or a_row.asset_type != 'Crypto':
        flash('Solo puedes editar aquí operaciones de criptomonedas.', 'warning')
        return redirect(url_for('crypto.dashboard'))

    form = CryptoTransactionForm()
    accounts = BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    form.account_id.choices = [
        (acc.id, f'{acc.broker.name} - {acc.account_name}')
        for acc in accounts
    ]
    if not form.account_id.choices:
        flash('No tienes ninguna cuenta activa.', 'warning')
        return redirect(url_for('portfolio.accounts_list'))

    form.submit.label.text = 'Guardar cambios'

    if form.validate_on_submit():
        account_id = int(form.account_id.data)
        symbol = form.symbol.data.strip().upper()
        currency = form.currency.data or 'EUR'

        target_asset = Asset.query.filter_by(
            symbol=symbol,
            asset_type='Crypto',
            currency=currency,
        ).first()
        if not target_asset:
            name = f"{symbol} (Crypto)"
            yahoo_suffix = f'-{currency}'
            target_asset = Asset(
                symbol=symbol,
                asset_type='Crypto',
                currency=currency,
                name=name,
                yahoo_suffix=yahoo_suffix,
            )
            db.session.add(target_asset)
            db.session.flush()

        qty = form.quantity.data
        price = form.price.data
        total = qty * price
        amount = -total if form.transaction_type.data == 'BUY' else total
        commission = form.commission.data or 0

        old_account_id = transaction.account_id
        old_txn_date = (
            transaction.transaction_date.date()
            if isinstance(transaction.transaction_date, datetime)
            else transaction.transaction_date
        )

        transaction.account_id = account_id
        transaction.asset_id = target_asset.id
        transaction.transaction_type = form.transaction_type.data
        transaction.transaction_date = datetime.combine(
            form.transaction_date.data, datetime.min.time()
        )
        transaction.settlement_date = form.transaction_date.data
        transaction.quantity = qty
        transaction.price = price
        transaction.amount = amount
        transaction.currency = currency
        transaction.commission = commission
        transaction.fees = 0
        transaction.notes = form.notes.data or None

        db.session.commit()

        if old_account_id != transaction.account_id:
            importer_old = CSVImporterV2(current_user.id, old_account_id)
            importer_old._recalculate_holdings()
        importer = CSVImporterV2(current_user.id, transaction.account_id)
        importer._recalculate_holdings()
        db.session.commit()

        d_new = form.transaction_date.data
        to_mark: list[date] = list(
            {d for d in (old_txn_date, d_new) if isinstance(d, date)}
        )
        if to_mark:
            CacheRebuildStateService.mark_for_dates(current_user.id, dates=to_mark)

        MetricsCacheService.invalidate(current_user.id)
        DashboardSummaryCacheService.invalidate(current_user.id)

        flash(f'✅ Operación actualizada: {qty} {symbol}', 'success')
        return redirect(url_for('crypto.dashboard'))

    if request.method == 'GET':
        form.account_id.data = transaction.account_id
        if transaction.asset:
            form.symbol.data = transaction.asset.symbol or ''
            form.currency.data = transaction.asset.currency or 'EUR'
        form.transaction_type.data = transaction.transaction_type
        form.quantity.data = float(transaction.quantity) if transaction.quantity else 0.0
        pr = transaction.price
        form.price.data = float(pr) if pr is not None else 0.0
        form.commission.data = float(transaction.commission or 0)
        if transaction.transaction_date:
            form.transaction_date.data = (
                transaction.transaction_date.date()
                if isinstance(transaction.transaction_date, datetime)
                else transaction.transaction_date
            )
        form.notes.data = transaction.notes

    return render_template(
        'crypto/transaction_form.html',
        form=form,
        brokers_for_account_modal=get_brokers_for_account_modal(),
        is_edit=True,
    )


@crypto_bp.route('/import')
@login_required
def import_csv():
    """Redirige a la subida de CSV de portfolio (soporta Revolut X)"""
    return redirect(url_for('portfolio.import_csv'))
