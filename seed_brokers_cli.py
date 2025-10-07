"""
Script para insertar brokers iniciales - ejecutar con: flask shell < seed_brokers_cli.py
O ejecutar: python seed_brokers_cli.py
"""
import os
from run import app
from app import db
from app.models import Broker

with app.app_context():
    brokers_data = [
        {'name': 'IBKR', 'full_name': 'Interactive Brokers'},
        {'name': 'DeGiro', 'full_name': 'DeGiro'},
        {'name': 'Manual', 'full_name': 'Entrada Manual'},
    ]
    
    for broker_info in brokers_data:
        existing = Broker.query.filter_by(name=broker_info['name']).first()
        if not existing:
            broker = Broker(**broker_info)
            db.session.add(broker)
            print(f"✅ Broker '{broker_info['name']}' creado")
        else:
            print(f"ℹ️  Broker '{broker_info['name']}' ya existe")
    
    db.session.commit()
    print("✅ Brokers inicializados correctamente")

