"""
Rutas para el módulo Metales (metales preciosos - Commodity)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime

from app import db
from app.models import BrokerAccount, Asset, Transaction
from app.forms.portfolio.account_forms import get_brokers_for_account_modal
from app.services.metales_metrics import (
    compute_metales_metrics,
    ensure_precious_metal_assets,
    PRECIOUS_METAL_YAHOO_SYMBOLS,
)
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


@metales_bp.route('/api/movimientos')
@login_required
def api_movimientos():
    """
    JSON: transacciones BUY/SELL de un metal en una cuenta (para modal en dashboard metales).
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
    if not asset or asset.asset_type != 'Commodity' or (asset.symbol or '') not in PRECIOUS_METAL_YAHOO_SYMBOLS:
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
        rows.append(
            {
                'id': t.id,
                'date': t.transaction_date.strftime('%d/%m/%Y %H:%M')
                if t.transaction_date
                else '',
                'type': t.transaction_type,
                'quantity': t.quantity,
                'price': t.price,
                'amount': t.amount,
                'currency': t.currency or 'EUR',
                'commission': float(t.commission or 0),
                'fees': float(t.fees or 0),
                'edit_url': url_for('metales.transaction_edit', id=t.id),
                'delete_url': url_for('portfolio.transaction_delete', id=t.id),
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


@metales_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Nueva compra o venta de metal"""
    from app.forms.metales_forms import MetalTransactionForm

    # Solo oro, plata, platino, paladio (futuros Yahoo); asegurar filas en BD
    ensure_precious_metal_assets()
    metals = (
        Asset.query.filter_by(asset_type='Commodity')
        .filter(Asset.symbol.in_(PRECIOUS_METAL_YAHOO_SYMBOLS))
        .order_by(Asset.symbol)
        .all()
    )
    if not metals:
        flash('No hay metales preciosos configurados. Contacta con soporte o ejecuta el seed: docs/scripts/seed_metales.py', 'warning')
        return redirect(url_for('metales.dashboard'))

    form = MetalTransactionForm()
    form.metal_id.choices = [(m.id, f"{m.symbol} - {m.name}") for m in metals]

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
        metal = Asset.query.get(form.metal_id.data)
        if not metal or metal.asset_type != 'Commodity' or (metal.symbol or '') not in PRECIOUS_METAL_YAHOO_SYMBOLS:
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
            account_id=account_id,
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

        recalculate_holdings(current_user.id, account_id)
        db.session.commit()
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService
        MetricsCacheService.invalidate(current_user.id)
        DashboardSummaryCacheService.invalidate(current_user.id)

        flash(f"✅ {'Compra' if form.transaction_type.data == 'BUY' else 'Venta'} registrada: {qty_g:.2f} g {metal.name}", 'success')
        return redirect(url_for('metales.dashboard'))

    return render_template(
        'metales/transaction_form.html',
        form=form,
        metals=metals,
        brokers_for_account_modal=get_brokers_for_account_modal(),
        is_edit=False,
    )


@metales_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def transaction_edit(id):
    """Editar compra/venta de metal (mismo formulario que /nueva)."""
    from app.forms.metales_forms import MetalTransactionForm
    from app.services.importer_v2 import CSVImporterV2
    from app.services.cache_rebuild_state_service import CacheRebuildStateService
    from app.services.metrics.cache import MetricsCacheService
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService

    ensure_precious_metal_assets()
    transaction = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if transaction.transaction_type not in ('BUY', 'SELL') or not transaction.asset_id:
        flash('Esta operación no se puede editar desde el módulo de metales.', 'warning')
        return redirect(url_for('metales.dashboard'))

    metal_row = db.session.get(Asset, transaction.asset_id)
    if (
        not metal_row
        or metal_row.asset_type != 'Commodity'
        or (metal_row.symbol or '') not in PRECIOUS_METAL_YAHOO_SYMBOLS
    ):
        flash('Solo puedes editar aquí operaciones de oro, plata, platino o paladio.', 'warning')
        return redirect(url_for('metales.dashboard'))

    metals = (
        Asset.query.filter_by(asset_type='Commodity')
        .filter(Asset.symbol.in_(PRECIOUS_METAL_YAHOO_SYMBOLS))
        .order_by(Asset.symbol)
        .all()
    )
    if not metals:
        flash('No hay metales preciosos configurados.', 'warning')
        return redirect(url_for('metales.dashboard'))

    form = MetalTransactionForm()
    form.metal_id.choices = [(m.id, f'{m.symbol} - {m.name}') for m in metals]
    accounts = BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    form.account_id.choices = [
        (acc.id, f'{acc.broker.name} - {acc.account_name}') for acc in accounts
    ]
    if not form.account_id.choices:
        flash('No tienes ninguna cuenta activa.', 'warning')
        return redirect(url_for('portfolio.accounts_list'))

    form.submit.label.text = 'Guardar cambios'

    if form.validate_on_submit():
        account_id = int(form.account_id.data)
        metal = Asset.query.get(form.metal_id.data)
        if not metal or metal.asset_type != 'Commodity' or (metal.symbol or '') not in PRECIOUS_METAL_YAHOO_SYMBOLS:
            flash('Metal no válido', 'error')
            return redirect(url_for('metales.transaction_edit', id=id))

        qty_g = form.quantity_grams.data
        if form.unit.data == 'oz':
            qty_g = form.quantity_grams.data * OZ_TROY_TO_G

        total_amount = form.total_amount.data
        price_per_unit = total_amount / qty_g if qty_g > 0 else 0
        amount = -total_amount if form.transaction_type.data == 'BUY' else total_amount

        old_account_id = transaction.account_id
        old_txn_date = (
            transaction.transaction_date.date()
            if isinstance(transaction.transaction_date, datetime)
            else transaction.transaction_date
        )

        transaction.account_id = account_id
        transaction.asset_id = metal.id
        transaction.transaction_type = form.transaction_type.data
        transaction.transaction_date = datetime.combine(
            form.transaction_date.data, datetime.min.time()
        )
        transaction.quantity = qty_g
        transaction.price = price_per_unit
        transaction.amount = amount
        transaction.currency = 'EUR'
        transaction.description = (
            f"{'Compra' if form.transaction_type.data == 'BUY' else 'Venta'} {qty_g:.2f} g {metal.name}"
        )
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

        flash(
            f"✅ Operación actualizada: {qty_g:.2f} g {metal.name}",
            'success',
        )
        return redirect(url_for('metales.dashboard'))

    if request.method == 'GET':
        form.account_id.data = transaction.account_id
        form.metal_id.data = transaction.asset_id
        form.transaction_type.data = transaction.transaction_type
        form.unit.data = 'g'
        form.quantity_grams.data = float(transaction.quantity) if transaction.quantity else 0.0
        form.total_amount.data = abs(float(transaction.amount or 0))
        if transaction.transaction_date:
            form.transaction_date.data = (
                transaction.transaction_date.date()
                if isinstance(transaction.transaction_date, datetime)
                else transaction.transaction_date
            )
        form.notes.data = transaction.notes

    return render_template(
        'metales/transaction_form.html',
        form=form,
        metals=metals,
        brokers_for_account_modal=get_brokers_for_account_modal(),
        is_edit=True,
    )
