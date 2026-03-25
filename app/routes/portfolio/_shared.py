"""
Helpers y cachés compartidos entre módulos de portfolio
"""
import json
import os
from threading import Lock

from app import db
from app.models import BrokerAccount, Broker

# Cache global para progreso de importación (thread-safe)
# NOTA: Con Gunicorn multi-worker, la memoria no se comparte. Usar get/set_import_progress_file().
import_progress_cache = {}
progress_lock = Lock()


def _import_progress_file_path(user_id):
    """Ruta del archivo de progreso (compartido entre workers de Gunicorn)."""
    from flask import current_app
    d = os.path.join(current_app.instance_path, 'import_progress')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'progress_{user_id}.json')


def get_import_progress(user_id):
    """Lee el progreso de importación desde archivo (visible por todos los workers)."""
    try:
        path = _import_progress_file_path(user_id)
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def set_import_progress(user_id, data):
    """Escribe el progreso de importación a archivo (visible por todos los workers)."""
    path = _import_progress_file_path(user_id)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

# Cache global para progreso de actualización de precios (thread-safe)
# NOTA: Con Gunicorn multi-worker la memoria no se comparte. En producción
# se usa get/set_price_update_progress (archivo) para que todos los workers vean el progreso.
price_update_progress_cache = {}
price_progress_lock = Lock()


def _price_update_progress_file_path(user_id):
    """Ruta del archivo de progreso de actualización de precios (compartido entre workers)."""
    from flask import current_app
    d = os.path.join(current_app.instance_path, 'import_progress')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'price_progress_{user_id}.json')


def get_price_update_progress(user_id):
    """Lee el progreso de actualización de precios desde archivo (visible por todos los workers)."""
    try:
        path = _price_update_progress_file_path(user_id)
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def set_price_update_progress(user_id, data, merge=False):
    """Escribe el progreso de actualización de precios a archivo (visible por todos los workers)."""
    path = _price_update_progress_file_path(user_id)
    if merge:
        try:
            with open(path) as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = {}
        existing.update(data)
        data = existing
    with open(path, 'w') as f:
        json.dump(data, f, default=str)

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
