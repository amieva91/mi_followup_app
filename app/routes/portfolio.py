"""
Rutas para gestión de portfolio
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
import os
from app.routes import portfolio_bp
from app import db
from app.models import (
    BrokerAccount, Asset, PortfolioHolding, 
    Transaction, Broker
)
from app.forms import (
    BrokerAccountForm, ManualTransactionForm
)
from app.services.csv_detector import detect_and_parse
from app.services.importer import CSVImporter

# Configuración de uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}


@portfolio_bp.route('/')
@login_required
def dashboard():
    """Dashboard del portfolio"""
    # Obtener todas las cuentas del usuario
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    # Obtener todas las posiciones actuales
    holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    # Calcular totales
    total_value = sum(h.current_value or 0 for h in holdings)
    total_cost = sum(h.total_cost for h in holdings)
    total_pl = total_value - total_cost if total_value > 0 else 0
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0
    
    return render_template(
        'portfolio/dashboard.html',
        accounts=accounts,
        holdings=holdings,
        total_value=total_value,
        total_cost=total_cost,
        total_pl=total_pl,
        total_pl_pct=total_pl_pct
    )


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
    form = BrokerAccountForm()
    
    if form.validate_on_submit():
        account = BrokerAccount(
            user_id=current_user.id,
            broker_id=form.broker_id.data,
            account_name=form.account_name.data,
            account_number=form.account_number.data,
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
        account.account_number = form.account_number.data
        account.base_currency = form.base_currency.data
        
        db.session.commit()
        flash(f'✅ Cuenta actualizada correctamente', 'success')
        return redirect(url_for('portfolio.accounts_list'))
    
    return render_template('portfolio/account_form.html', form=form, title='Editar Cuenta', account=account)


@portfolio_bp.route('/accounts/<int:id>/delete', methods=['POST'])
@login_required
def account_delete(id):
    """Eliminar cuenta de broker y todos sus datos asociados"""
    account = BrokerAccount.query.get_or_404(id)
    
    if account.user_id != current_user.id:
        flash('❌ No tienes permiso para eliminar esta cuenta', 'error')
        return redirect(url_for('portfolio.accounts_list'))
    
    # Contar datos asociados para mostrar en el mensaje
    num_holdings = PortfolioHolding.query.filter_by(account_id=id).count()
    num_transactions = Transaction.query.filter_by(account_id=id).count()
    
    account_name = account.account_name
    
    # Borrar en cascada manual (por si las FK no tienen CASCADE)
    # 1. Borrar métricas
    from app.models.metrics import PortfolioMetrics
    PortfolioMetrics.query.filter_by(account_id=id).delete()
    
    # 2. Borrar cash flows
    from app.models.transaction import CashFlow
    CashFlow.query.filter_by(account_id=id).delete()
    
    # 3. Borrar transacciones
    Transaction.query.filter_by(account_id=id).delete()
    
    # 4. Borrar holdings
    PortfolioHolding.query.filter_by(account_id=id).delete()
    
    # 5. Borrar la cuenta
    db.session.delete(account)
    db.session.commit()
    
    flash(
        f'🗑️ Cuenta "{account_name}" eliminada permanentemente. '
        f'Se borraron {num_transactions} transacciones y {num_holdings} posiciones.',
        'success'
    )
    return redirect(url_for('portfolio.accounts_list'))


@portfolio_bp.route('/holdings')
@login_required
def holdings_list():
    """Lista de posiciones actuales (agrupadas por asset)"""
    from collections import defaultdict
    
    # Obtener todos los holdings
    all_holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    # Agrupar por asset_id
    grouped = defaultdict(lambda: {
        'asset': None,
        'total_quantity': 0,
        'total_cost': 0,
        'accounts': [],
        'first_purchase_date': None,
        'last_transaction_date': None
    })
    
    for holding in all_holdings:
        asset_id = holding.asset_id
        group = grouped[asset_id]
        
        # Datos del asset (tomar del primer holding)
        if group['asset'] is None:
            group['asset'] = holding.asset
        
        # Sumar cantidades y costes
        group['total_quantity'] += holding.quantity
        group['total_cost'] += holding.total_cost
        
        # Agregar cuenta a la lista
        group['accounts'].append({
            'broker': holding.account.broker.name,
            'account_name': holding.account.account_name,
            'quantity': holding.quantity,
            'average_buy_price': holding.average_buy_price
        })
        
        # Fechas (usar la más antigua para first_purchase y la más reciente para last_transaction)
        if group['first_purchase_date'] is None or holding.first_purchase_date < group['first_purchase_date']:
            group['first_purchase_date'] = holding.first_purchase_date
        
        if group['last_transaction_date'] is None or holding.last_transaction_date > group['last_transaction_date']:
            group['last_transaction_date'] = holding.last_transaction_date
    
    # Convertir a lista y calcular precio medio ponderado
    holdings_unified = []
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['asset_id'] = asset_id
        holdings_unified.append(data)
    
    # Ordenar por símbolo
    holdings_unified.sort(key=lambda x: x['asset'].symbol if x['asset'] else '')
    
    return render_template('portfolio/holdings.html', holdings=holdings_unified, unified=True)


@portfolio_bp.route('/transactions')
@login_required
def transactions_list():
    """Lista de transacciones con filtros"""
    from datetime import datetime
    
    # Query base
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Aplicar filtros
    filtered = False
    
    # Filtro por símbolo o ISIN
    symbol = request.args.get('symbol', '').strip()
    if symbol:
        filtered = True
        # Buscar assets que coincidan con el símbolo o ISIN
        assets = Asset.query.filter(
            db.or_(
                Asset.symbol.ilike(f'%{symbol}%'),
                Asset.isin.ilike(f'%{symbol}%')
            )
        ).all()
        asset_ids = [a.id for a in assets]
        if asset_ids:
            query = query.filter(Transaction.asset_id.in_(asset_ids))
        else:
            # No hay assets que coincidan, retornar lista vacía
            query = query.filter(Transaction.asset_id == -1)
    
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
    
    # Ordenar y limitar
    transactions = query.order_by(Transaction.transaction_date.desc()).limit(100).all()
    
    # Obtener todas las cuentas para el selector
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(BrokerAccount.broker_id, BrokerAccount.account_name).all()
    
    return render_template('portfolio/transactions.html', 
                          transactions=transactions,
                          accounts=accounts,
                          filtered=filtered)


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
        
        # Actualizar transacción
        old_account_id = transaction.account_id
        transaction.account_id = form.account_id.data
        transaction.transaction_type = form.transaction_type.data
        transaction.transaction_date = form.transaction_date.data
        transaction.quantity = form.quantity.data
        transaction.price = form.price.data
        transaction.amount = form.quantity.data * form.price.data
        transaction.currency = form.currency.data
        transaction.commission = form.commission.data
        transaction.fees = form.fees.data
        transaction.tax = form.tax.data
        transaction.notes = form.notes.data
        
        db.session.commit()
        
        # Recalcular holdings de la(s) cuenta(s) afectada(s)
        from app.services.importer import CSVImporter
        
        # Recalcular cuenta antigua si cambió
        if old_account_id != transaction.account_id:
            importer_old = CSVImporter(current_user.id, old_account_id)
            importer_old._recalculate_holdings()
        
        # Recalcular cuenta actual
        importer = CSVImporter(current_user.id, transaction.account_id)
        importer._recalculate_holdings()
        
        db.session.commit()
        
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
                          action='edit')


@portfolio_bp.route('/transactions/new', methods=['GET', 'POST'])
@login_required
def transaction_new():
    """Registrar nueva transacción manual"""
    form = ManualTransactionForm()
    
    if form.validate_on_submit():
        # Buscar o crear el activo
        asset = Asset.query.filter_by(symbol=form.symbol.data, currency=form.currency.data).first()
        if not asset:
            asset = Asset(
                symbol=form.symbol.data,
                isin=form.isin.data,
                name=form.asset_name.data,
                asset_type=form.asset_type.data,
                currency=form.currency.data
            )
            db.session.add(asset)
            db.session.flush()
        
        # Calcular monto
        amount = form.quantity.data * form.price.data
        if form.transaction_type.data == 'BUY':
            amount = -amount  # Compra es negativo (sale dinero)
        
        # Crear transacción
        transaction = Transaction(
            user_id=current_user.id,
            account_id=form.account_id.data,
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
        
        # Actualizar o crear holding
        holding = PortfolioHolding.query.filter_by(
            user_id=current_user.id,
            account_id=form.account_id.data,
            asset_id=asset.id
        ).first()
        
        if form.transaction_type.data == 'BUY':
            if holding:
                # Actualizar holding existente
                holding.add_purchase(
                    quantity=form.quantity.data,
                    price=form.price.data,
                    total_cost=abs(amount) + form.commission.data + form.fees.data + form.tax.data
                )
                holding.last_transaction_date = form.transaction_date.data
            else:
                # Crear nuevo holding
                total_cost = abs(amount) + form.commission.data + form.fees.data + form.tax.data
                holding = PortfolioHolding(
                    user_id=current_user.id,
                    account_id=form.account_id.data,
                    asset_id=asset.id,
                    quantity=form.quantity.data,
                    average_buy_price=form.price.data,
                    total_cost=total_cost,
                    first_purchase_date=form.transaction_date.data,
                    last_transaction_date=form.transaction_date.data
                )
                db.session.add(holding)
        
        elif form.transaction_type.data == 'SELL':
            if holding:
                # Calcular P&L (simplificado por ahora)
                cost_basis = holding.average_buy_price * form.quantity.data
                revenue = abs(amount) - form.commission.data - form.fees.data - form.tax.data
                realized_pl = revenue - cost_basis
                transaction.realized_pl = realized_pl
                
                if cost_basis > 0:
                    transaction.realized_pl_pct = (realized_pl / cost_basis) * 100
                
                # Actualizar holding
                holding.subtract_sale(form.quantity.data, realized_pl)
                holding.last_transaction_date = form.transaction_date.data
        
        db.session.commit()
        
        flash(f'✅ Transacción de {form.transaction_type.data} registrada correctamente', 'success')
        return redirect(url_for('portfolio.transactions_list'))
    
    return render_template('portfolio/transaction_form.html', form=form, title='Nueva Transacción')


# ==================== CSV IMPORT ====================

def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@portfolio_bp.route('/import')
@login_required
def import_csv():
    """Formulario para subir CSV"""
    # Obtener cuentas del usuario
    accounts = BrokerAccount.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    return render_template('portfolio/import_csv.html', accounts=accounts, title='Importar CSV')


@portfolio_bp.route('/import/process', methods=['POST'])
@login_required
def import_csv_process():
    """Procesa uno o múltiples archivos CSV subidos"""
    # Verificar que se enviaron archivos
    if 'csv_files' not in request.files:
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    files = request.files.getlist('csv_files')
    
    if not files or len(files) == 0 or files[0].filename == '':
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    # Validar que todos son CSV
    for file in files:
        if not allowed_file(file.filename):
            flash(f'❌ Archivo no válido: {file.filename} (solo se permiten archivos CSV)', 'error')
            return redirect(url_for('portfolio.import_csv'))
    
    # Obtener cuenta seleccionada
    account_id = request.form.get('account_id')
    if not account_id:
        flash('❌ Debes seleccionar una cuenta', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    account = BrokerAccount.query.get(account_id)
    if not account or account.user_id != current_user.id:
        flash('❌ Cuenta no válida', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    # Asegurar que existe el directorio de uploads
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Procesar cada archivo
    total_stats = {
        'files_processed': 0,
        'files_failed': 0,
        'transactions_created': 0,
        'transactions_skipped': 0,
        'holdings_created': 0,
        'dividends_created': 0,
        'assets_created': 0
    }
    
    failed_files = []
    
    for file in files:
        filepath = None
        try:
            # Guardar archivo temporalmente
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"temp_{current_user.id}_{filename}")
            file.save(filepath)
            
            # Detectar y parsear
            parsed_data = detect_and_parse(filepath)
            
            # Importar a BD (el importer detecta automáticamente duplicados entre archivos)
            importer = CSVImporter(user_id=current_user.id, broker_account_id=account.id)
            stats = importer.import_data(parsed_data)
            
            # Acumular estadísticas
            total_stats['files_processed'] += 1
            total_stats['transactions_created'] += stats['transactions_created']
            total_stats['transactions_skipped'] += stats['transactions_skipped']
            total_stats['holdings_created'] += stats['holdings_created']
            total_stats['dividends_created'] += stats['dividends_created']
            total_stats['assets_created'] += stats['assets_created']
            
            # Eliminar archivo temporal
            if os.path.exists(filepath):
                os.remove(filepath)
                
        except Exception as e:
            # Registrar archivo fallido
            total_stats['files_failed'] += 1
            failed_files.append((file.filename, str(e)))
            
            # Eliminar archivo temporal si existe
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
    
    # Mensajes de resultado
    if total_stats['files_processed'] > 0:
        if len(files) == 1:
            flash(f'✅ CSV importado correctamente', 'success')
        else:
            flash(f'✅ {total_stats["files_processed"]} archivos importados correctamente', 'success')
        
        flash(f'📊 {total_stats["transactions_created"]} transacciones | {total_stats["holdings_created"]} holdings nuevos | {total_stats["dividends_created"]} dividendos', 'info')
        
        if total_stats['transactions_skipped'] > 0:
            flash(f'ℹ️  {total_stats["transactions_skipped"]} transacciones duplicadas (omitidas entre archivos)', 'info')
    
    if total_stats['files_failed'] > 0:
        flash(f'⚠️  {total_stats["files_failed"]} archivos fallaron al importarse:', 'warning')
        for filename, error in failed_files:
            flash(f'  • {filename}: {error}', 'error')
    
    if total_stats['files_processed'] == 0:
        flash('❌ No se pudo importar ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    return redirect(url_for('portfolio.dashboard'))

