"""
Helpers y cachés compartidos entre módulos de portfolio
"""
from threading import Lock

from app import db
from app.models import BrokerAccount, Broker

# Cache global para progreso de importación (thread-safe)
import_progress_cache = {}
progress_lock = Lock()

# Cache global para progreso de actualización de precios (thread-safe)
price_update_progress_cache = {}
price_progress_lock = Lock()

# Configuración de uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}


def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_or_create_broker_account(user_id, broker_format):
    """
    Obtiene o crea automáticamente la cuenta del broker según el formato CSV detectado

    Args:
        user_id: ID del usuario
        broker_format: Formato detectado ('IBKR', 'DEGIRO_TRANSACTIONS', 'DEGIRO_ACCOUNT', etc.)

    Returns:
        BrokerAccount: La cuenta existente o recién creada
    """
    broker_format_lower = broker_format.lower()

    if 'degiro' in broker_format_lower:
        broker_search_name = 'DeGiro'
        account_default_name = 'Degiro'
    elif broker_format_lower == 'ibkr':
        broker_search_name = 'IBKR'
        account_default_name = 'IBKR'
    elif broker_format_lower == 'revolut_x':
        broker_search_name = 'Revolut'
        account_default_name = 'Revolut Crypto'
    else:
        broker_search_name = broker_format.upper()
        account_default_name = broker_format.upper()

    broker = Broker.query.filter(
        db.func.lower(Broker.name).like(f'%{broker_search_name.lower()}%')
    ).first()

    if not broker:
        broker_full_names = {
            'IBKR': 'Interactive Brokers',
            'DeGiro': 'DeGiro',
            'Degiro': 'DeGiro',
            'Revolut': 'Revolut X - Criptomonedas',
        }
        full_name = broker_full_names.get(broker_search_name, broker_search_name)
        broker = Broker(
            name=broker_search_name,
            full_name=full_name,
            is_active=True
        )
        db.session.add(broker)
        db.session.flush()

    account = BrokerAccount.query.filter_by(
        user_id=user_id,
        broker_id=broker.id,
        is_active=True
    ).first()

    if not account:
        account = BrokerAccount(
            user_id=user_id,
            broker_id=broker.id,
            account_name=account_default_name,
            base_currency='EUR',
            is_active=True
        )
        db.session.add(account)
        db.session.flush()

    db.session.commit()
    return account
