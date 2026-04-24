"""
Rutas de transacciones
"""
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app import db
from app.models import BrokerAccount, Asset, Transaction, PortfolioHolding
from app.forms import ManualTransactionForm

@portfolio_bp.route('/transactions')
@login_required
def transactions_list():
    """Lista de transacciones con filtros"""
    
    # Query base
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Aplicar filtros
    filtered = False
    
    # Filtro por ISIN / símbolo / nombre
    symbol = request.args.get('symbol', '').strip()
    if symbol:
        filtered = True
        # Evitar 2 consultas (assets->ids->IN). Filtrar con JOIN directo.
        query = query.join(Asset, Transaction.asset_id == Asset.id).filter(
            db.or_(
                Asset.symbol.ilike(f'%{symbol}%'),
                Asset.isin.ilike(f'%{symbol}%'),
                Asset.name.ilike(f'%{symbol}%'),
            )
        )
    
    # Filtro por tipo de transacción
    txn_type = request.args.get('type', '').strip()
    if txn_type:
        filtered = True
        query = query.filter_by(transaction_type=txn_type)
    
    # Filtro por cuenta
    account_id = request.args.get('account', '').strip()
    if account_id:
        filtered = True
        try:
            query = query.filter_by(account_id=int(account_id))
        except ValueError:
            pass

    # Filtro por tipo de activo (Stock, ETF, Crypto, Commodity)
    asset_type_filter = request.args.get('asset_type', '').strip()
    if asset_type_filter:
        filtered = True
        asset_ids_subq = db.session.query(Asset.id).filter(Asset.asset_type == asset_type_filter)
        query = query.filter(Transaction.asset_id.in_(asset_ids_subq))

    # Filtro por fecha desde
    date_from = request.args.get('date_from', '').strip()
    if date_from:
        filtered = True
        try:
            date_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date >= date_obj)
        except ValueError:
            pass
    
    # Filtro por fecha hasta
    date_to = request.args.get('date_to', '').strip()
    if date_to:
        filtered = True
        try:
            date_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date <= date_obj)
        except ValueError:
            pass
    
    # Filtro: Dividendos a revisar (dividendos no EUR)
    dividends_review = request.args.get('dividends_review', '').strip()
    if dividends_review:
        filtered = True
        query = query.filter(
            Transaction.transaction_type == 'DIVIDEND',
            Transaction.currency != 'EUR'
        )
    
    # Filtro: Assets sin enriquecer (sin symbol o sin ibkr_exchange en AssetRegistry)
    unenriched_assets = request.args.get('unenriched_assets', '').strip()
    if unenriched_assets:
        from app.models import AssetRegistry
        filtered = True
        
        # Buscar assets que necesitan enriquecimiento
        unenriched_registries = AssetRegistry.query.filter(
            db.or_(
                AssetRegistry.symbol.is_(None),
                AssetRegistry.ibkr_exchange.is_(None)
            )
        ).all()
        
        # Obtener ISINs
        unenriched_isins = [r.isin for r in unenriched_registries]
        
        # Filtrar transacciones de esos assets
        if unenriched_isins:
            assets = Asset.query.filter(Asset.isin.in_(unenriched_isins)).all()
            asset_ids = [a.id for a in assets]
            if asset_ids:
                query = query.filter(Transaction.asset_id.in_(asset_ids))
            else:
                query = query.filter(Transaction.asset_id == -1)
        else:
            query = query.filter(Transaction.asset_id == -1)
    
    # Ordenamiento dinámico
    sort_by = request.args.get('sort_by', 'transaction_date').strip()
    sort_order = request.args.get('sort_order', 'desc').strip()
    
    # Mapeo de campos de ordenamiento
    sort_fields = {
        'transaction_date': Transaction.transaction_date,
        'transaction_type': Transaction.transaction_type,
        'amount': Transaction.amount,
        'asset': Asset.symbol,  # Join con Asset
        'account': BrokerAccount.account_name  # Join con BrokerAccount
    }
    
    # Aplicar joins si es necesario
    if sort_by in ['asset', 'account']:
        if sort_by == 'asset':
            query = query.outerjoin(Asset, Transaction.asset_id == Asset.id)
        elif sort_by == 'account':
            query = query.join(BrokerAccount, Transaction.account_id == BrokerAccount.id)
    
    # Aplicar ordenamiento
    if sort_by in sort_fields:
        order_field = sort_fields[sort_by]
        if sort_order == 'asc':
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())
    else:
        # Ordenamiento por defecto
        query = query.order_by(Transaction.transaction_date.desc())
    
    # Paginación (100 transacciones por página)
    page = request.args.get('page', 1, type=int)
    per_page = 100
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    transactions = pagination.items
    
    # Obtener todas las cuentas para el selector
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(BrokerAccount.broker_id, BrokerAccount.account_name).all()

    # Si es búsqueda AJAX, devolver solo el fragmento (tabla + paginación) para reducir payload.
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return render_template(
            'portfolio/_transactions_results.html',
            transactions=transactions,
            pagination=pagination,
        )

    return render_template(
        'portfolio/transactions.html',
        transactions=transactions,
        accounts=accounts,
        filtered=filtered,
        pagination=pagination,
    )




@portfolio_bp.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def transaction_edit(id):
    """Editar transacción existente"""
    transaction = Transaction.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()
    
    form = ManualTransactionForm()
    
    # Poblar choices dinámicamente
    form.account_id.choices = [
        (acc.id, f'{acc.broker.name} - {acc.account_name}')
        for acc in BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    ]
    
    if form.validate_on_submit():
        # Actualizar datos del asset si cambió
        asset = transaction.asset
        if asset:
            asset.symbol = form.symbol.data
            asset.isin = form.isin.data if form.isin.data else asset.isin
            asset.name = form.asset_name.data
            asset.asset_type = form.asset_type.data
            asset.currency = form.currency.data
            # Actualizar identificadores de mercado
            asset.exchange = form.exchange.data if form.exchange.data else asset.exchange
            asset.mic = form.mic.data if form.mic.data else asset.mic
            asset.yahoo_suffix = form.yahoo_suffix.data if form.yahoo_suffix.data else asset.yahoo_suffix
        
        # Actualizar transacción
        old_account_id = transaction.account_id
        transaction.account_id = form.account_id.data
        transaction.transaction_type = form.transaction_type.data
        transaction.transaction_date = form.transaction_date.data
        transaction.quantity = form.quantity.data
        transaction.price = form.price.data
        # Mismo criterio que transaction_new: compra = flujo de caja negativo, venta = positivo
        amount = (form.quantity.data or 0) * (form.price.data or 0)
        if form.transaction_type.data == 'BUY':
            amount = -amount
        transaction.amount = amount
        transaction.currency = form.currency.data
        transaction.commission = form.commission.data
        transaction.fees = form.fees.data
        transaction.tax = form.tax.data
        transaction.notes = form.notes.data
        
        db.session.commit()
        
        # Recalcular holdings de la(s) cuenta(s) afectada(s)
        from app.services.importer_v2 import CSVImporterV2
        
        # Recalcular cuenta antigua si cambió
        if old_account_id != transaction.account_id:
            importer_old = CSVImporterV2(current_user.id, old_account_id)
            importer_old._recalculate_holdings()
        
        # Recalcular cuenta actual
        importer = CSVImporterV2(current_user.id, transaction.account_id)
        importer._recalculate_holdings()
        
        db.session.commit()
        
        # Encolar rebuild para worker (criterio unificado por fecha)
        from app.services.cache_rebuild_state_service import CacheRebuildStateService
        txn_date = transaction.transaction_date.date() if isinstance(transaction.transaction_date, datetime) else transaction.transaction_date
        CacheRebuildStateService.mark_for_dates(current_user.id, dates=[txn_date])
        
        flash('✅ Transacción actualizada correctamente. Holdings recalculados.', 'success')
        return redirect(url_for('portfolio.transactions_list'))
    
    # Prellenar formulario en GET
    if request.method == 'GET' and transaction.asset:
        form.account_id.data = transaction.account_id
        form.symbol.data = transaction.asset.symbol
        form.isin.data = transaction.asset.isin
        form.asset_name.data = transaction.asset.name
        form.asset_type.data = transaction.asset.asset_type
        form.currency.data = transaction.currency
        # Identificadores de mercado
        form.exchange.data = transaction.asset.exchange
        form.mic.data = transaction.asset.mic
        form.yahoo_suffix.data = transaction.asset.yahoo_suffix
        # Datos de transacción
        form.transaction_type.data = transaction.transaction_type
        form.transaction_date.data = transaction.transaction_date
        form.quantity.data = transaction.quantity
        form.price.data = float(transaction.price) if transaction.price else 0
        form.commission.data = float(transaction.commission) if transaction.commission else 0
        form.fees.data = float(transaction.fees) if transaction.fees else 0
        form.tax.data = float(transaction.tax) if transaction.tax else 0
        form.notes.data = transaction.notes
    
    return render_template('portfolio/transaction_form.html', 
                          form=form, 
                          title='Editar Transacción',
                          action='edit',
                          transaction=transaction)




@portfolio_bp.route('/transactions/<int:id>/delete', methods=['POST'])
@login_required
def transaction_delete(id):
    """Eliminar transacción existente"""
    transaction = Transaction.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()
    
    # Guardar cuenta para recalcular holdings después + fecha para cachés HIST/NOW
    account_id = transaction.account_id
    txn_date = transaction.transaction_date.date() if isinstance(transaction.transaction_date, datetime) else transaction.transaction_date
    asset_symbol = transaction.asset.symbol if transaction.asset else transaction.transaction_type
    
    # Eliminar transacción
    db.session.delete(transaction)
    db.session.commit()
    
    # Recalcular holdings de la cuenta afectada
    from app.services.importer_v2 import CSVImporterV2
    importer = CSVImporterV2(current_user.id, account_id)
    importer._recalculate_holdings()
    db.session.commit()
    
    # Encolar rebuild para worker (criterio unificado por fecha)
    from app.services.cache_rebuild_state_service import CacheRebuildStateService
    CacheRebuildStateService.mark_for_dates(current_user.id, dates=[txn_date])
    
    flash(f'✅ Transacción de {asset_symbol} eliminada correctamente. Holdings recalculados.', 'success')
    return redirect(url_for('portfolio.transactions_list'))






@portfolio_bp.route('/transactions/new', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Registrar nueva transacción manual"""
    form = ManualTransactionForm()
    
    # Poblar choices con cuentas del usuario
    accounts = BrokerAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
    form.account_id.choices = [
        (acc.id, f'{acc.broker.name} - {acc.account_name}')
        for acc in accounts
    ]
    if not form.account_id.choices:
        flash('No tienes ninguna cuenta. Crea una en Cuentas antes de registrar transacciones.', 'warning')
        return redirect(url_for('portfolio.accounts_list'))
    
    if form.validate_on_submit():
        account_id = int(form.account_id.data)
        # Buscar o crear el activo
        asset = Asset.query.filter_by(symbol=form.symbol.data, currency=form.currency.data).first()
        if not asset:
            asset = Asset(
                symbol=form.symbol.data,
                isin=form.isin.data,
                name=form.asset_name.data,
                asset_type=form.asset_type.data,
                currency=form.currency.data,
                exchange=form.exchange.data,
                mic=form.mic.data,
                yahoo_suffix=form.yahoo_suffix.data
            )
            db.session.add(asset)
            db.session.flush()
        else:
            # Actualizar asset existente con nuevos datos si se proporcionan
            if form.exchange.data:
                asset.exchange = form.exchange.data
            if form.mic.data:
                asset.mic = form.mic.data
            if form.yahoo_suffix.data:
                asset.yahoo_suffix = form.yahoo_suffix.data
        
        # Calcular monto
        amount = form.quantity.data * form.price.data
        if form.transaction_type.data == 'BUY':
            amount = -amount  # Compra es negativo (sale dinero)
        
        # Crear transacción
        transaction = Transaction(
            user_id=current_user.id,
            account_id=account_id,
            asset_id=asset.id,
            transaction_type=form.transaction_type.data,
            transaction_date=datetime.combine(form.transaction_date.data, datetime.min.time()),
            settlement_date=form.transaction_date.data,
            quantity=form.quantity.data,
            price=form.price.data,
            amount=amount,
            currency=form.currency.data,
            commission=form.commission.data,
            fees=form.fees.data,
            tax=form.tax.data,
            notes=form.notes.data,
            source='MANUAL'
        )
        db.session.add(transaction)
        db.session.flush()  # Obtener ID de la transacción
        
        # Recalcular holdings usando FIFO (el método correcto)
        from app.services.fifo_calculator import FIFOCalculator
        
        # Obtener todas las transacciones de este asset en esta cuenta
        all_transactions = Transaction.query.filter_by(
            user_id=current_user.id,
            account_id=account_id,
            asset_id=asset.id
        ).order_by(Transaction.transaction_date, Transaction.id).all()
        
        # Calcular holding con FIFO
        fifo = FIFOCalculator()
        
        # Procesar todas las transacciones EXCEPTO la actual
        for t in all_transactions:
            if t.id == transaction.id:
                continue  # Saltar la transacción que acabamos de crear
            
            if t.transaction_type == 'BUY':
                fifo.add_buy(
                    quantity=t.quantity,
                    price=t.price,
                    date=t.transaction_date,
                    total_cost=abs(t.amount) + (t.commission or 0) + (t.fees or 0) + (t.tax or 0)
                )
            elif t.transaction_type == 'SELL':
                fifo.add_sell(
                    quantity=t.quantity,
                    date=t.transaction_date
                )
        
        # Ahora procesar la transacción actual
        cost_basis_of_sale = None
        commission = form.commission.data or 0.0
        fees = form.fees.data or 0.0
        tax = form.tax.data or 0.0
        if form.transaction_type.data == 'BUY':
            fifo.add_buy(
                quantity=form.quantity.data,
                price=form.price.data,
                date=form.transaction_date.data,
                total_cost=abs(amount) + commission + fees + tax
            )
        elif form.transaction_type.data == 'SELL':
            # add_sell retorna el coste de las acciones vendidas (base de coste)
            cost_basis_of_sale = fifo.add_sell(
                quantity=form.quantity.data,
                date=form.transaction_date.data
            )
        
        # Obtener o crear holding
        holding = PortfolioHolding.query.filter_by(
            user_id=current_user.id,
            account_id=account_id,
            asset_id=asset.id
        ).first()
        
        current_position = fifo.get_current_position()
        
        if current_position['quantity'] > 0:
            # Hay posición abierta
            if holding:
                holding.quantity = current_position['quantity']
                holding.average_buy_price = current_position['average_buy_price']
                holding.total_cost = current_position['total_cost']
                holding.last_transaction_date = form.transaction_date.data
            else:
                holding = PortfolioHolding(
                    user_id=current_user.id,
                    account_id=account_id,
                    asset_id=asset.id,
                    quantity=current_position['quantity'],
                    average_buy_price=current_position['average_buy_price'],
                    total_cost=current_position['total_cost'],
                    first_purchase_date=form.transaction_date.data,
                    last_transaction_date=form.transaction_date.data
                )
                db.session.add(holding)
        else:
            # Posición cerrada, eliminar holding si existe
            if holding:
                db.session.delete(holding)
        
        # Calcular P&L realizado si es SELL
        if form.transaction_type.data == 'SELL' and cost_basis_of_sale is not None:
            # Revenue = (precio_venta * cantidad) - comisiones - fees - tax
            revenue = abs(amount) - commission - fees - tax
            # P&L = revenue - coste de compra
            realized_pl = revenue - float(cost_basis_of_sale)
            transaction.realized_pl = realized_pl
            
            # Calcular % de ganancia
            if float(cost_basis_of_sale) > 0:
                transaction.realized_pl_pct = (realized_pl / float(cost_basis_of_sale)) * 100
        
        db.session.commit()
        
        # Encolar rebuild para worker (criterio unificado por fecha)
        from app.services.cache_rebuild_state_service import CacheRebuildStateService
        d = form.transaction_date.data
        CacheRebuildStateService.mark_for_dates(current_user.id, dates=[d])
        
        action_text = 'compra' if form.transaction_type.data == 'BUY' else 'venta'
        flash(f'✅ {form.transaction_type.data} de {form.symbol.data} registrada correctamente', 'success')
        return redirect(url_for('portfolio.holdings_list'))
    
    return render_template('portfolio/transaction_form.html', form=form, transaction=None, action='new', title='Nueva Transacción')


# ==================== METRICS CACHE ====================

