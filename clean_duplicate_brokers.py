"""
Script para limpiar brokers duplicados y dejar solo los predefinidos
"""
from app import create_app, db
from app.models import Broker

app = create_app('development')

with app.app_context():
    # Brokers que deben existir (predefinidos)
    valid_brokers = ['IBKR - Interactive Brokers', 'DeGiro - DeGiro', 'Manual - Entrada Manual']
    
    # Obtener todos los brokers
    all_brokers = Broker.query.all()
    
    print(f"📊 Brokers existentes ({len(all_brokers)}):")
    for broker in all_brokers:
        print(f"  - ID {broker.id}: {broker.name}")
    
    # Identificar duplicados
    duplicates = [b for b in all_brokers if b.name not in valid_brokers]
    
    if duplicates:
        print(f"\n🗑️  Brokers a eliminar ({len(duplicates)}):")
        for broker in duplicates:
            print(f"  - ID {broker.id}: {broker.name}")
        
        confirm = input("\n¿Deseas eliminar estos brokers duplicados? (s/n): ")
        if confirm.lower() == 's':
            for broker in duplicates:
                db.session.delete(broker)
            db.session.commit()
            print("✅ Brokers duplicados eliminados correctamente")
        else:
            print("❌ Operación cancelada")
    else:
        print("\n✅ No hay brokers duplicados. Solo existen los predefinidos.")

