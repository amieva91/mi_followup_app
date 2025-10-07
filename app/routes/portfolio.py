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
    """Lista de posiciones actuales"""
    holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id
    ).filter(PortfolioHolding.quantity > 0).all()
    
    return render_template('portfolio/holdings.html', holdings=holdings)


@portfolio_bp.route('/transactions')
@login_required
def transactions_list():
    """Lista de transacciones"""
    transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.transaction_date.desc()).limit(100).all()
    
    return render_template('portfolio/transactions.html', transactions=transactions)


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
    """Procesa el archivo CSV subido"""
    # Verificar que se envió un archivo
    if 'csv_file' not in request.files:
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    file = request.files['csv_file']
    
    if file.filename == '':
        flash('❌ No se seleccionó ningún archivo', 'error')
        return redirect(url_for('portfolio.import_csv'))
    
    if not allowed_file(file.filename):
        flash('❌ Solo se permiten archivos CSV', 'error')
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
    
    try:
        # Guardar archivo temporalmente
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, f"temp_{current_user.id}_{filename}")
        
        # Asegurar que existe el directorio
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        file.save(filepath)
        
        # Detectar y parsear
        parsed_data = detect_and_parse(filepath)
        
        # Importar a BD
        importer = CSVImporter(user_id=current_user.id, broker_account_id=account.id)
        stats = importer.import_data(parsed_data)
        
        # Eliminar archivo temporal
        os.remove(filepath)
        
        # Mensaje de éxito
        flash(f'✅ CSV importado correctamente', 'success')
        flash(f'📊 {stats["transactions_created"]} transacciones | {stats["holdings_created"]} holdings nuevos | {stats["dividends_created"]} dividendos', 'info')
        
        if stats['transactions_skipped'] > 0:
            flash(f'ℹ️  {stats["transactions_skipped"]} transacciones duplicadas (omitidas)', 'info')
        
        return redirect(url_for('portfolio.dashboard'))
        
    except Exception as e:
        # Eliminar archivo temporal si existe
        if os.path.exists(filepath):
            os.remove(filepath)
        
        flash(f'❌ Error al procesar CSV: {str(e)}', 'error')
        return redirect(url_for('portfolio.import_csv'))

