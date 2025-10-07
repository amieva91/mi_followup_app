"""
Script para insertar brokers iniciales
"""
import sys
import os

# Añadir el directorio padre al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import db, create_app
from app.models import Broker


def seed_brokers():
    """Inserta los brokers iniciales si no existen"""
    
    brokers_data = [
        {'name': 'IBKR', 'full_name': 'Interactive Brokers'},
        {'name': 'DeGiro', 'full_name': 'DeGiro'},
        {'name': 'Manual', 'full_name': 'Entrada Manual'},
    ]
    
    for broker_info in brokers_data:
        # Verificar si ya existe
        existing = Broker.query.filter_by(name=broker_info['name']).first()
        if not existing:
            broker = Broker(**broker_info)
            db.session.add(broker)
            print(f"✅ Broker '{broker_info['name']}' creado")
        else:
            print(f"ℹ️  Broker '{broker_info['name']}' ya existe")
    
    db.session.commit()
    print("✅ Brokers inicializados correctamente")


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV') or 'default')
    with app.app_context():
        seed_brokers()

