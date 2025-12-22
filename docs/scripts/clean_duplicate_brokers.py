"""
Script para limpiar brokers duplicados y dejar solo los predefinidos
"""
from app import create_app, db
from app.models import Broker, BrokerAccount

app = create_app('development')

with app.app_context():
    # Brokers que deben existir (predefinidos) - IDs 1, 2, 3
    valid_broker_ids = [1, 2, 3]
    
    # Obtener todos los brokers
    all_brokers = Broker.query.all()
    
    print(f"📊 Brokers existentes ({len(all_brokers)}):")
    for broker in all_brokers:
        print(f"  - ID {broker.id}: {broker.name}")
    
    # Identificar duplicados (IDs > 3)
    duplicates = [b for b in all_brokers if b.id not in valid_broker_ids]
    
    if duplicates:
        print(f"\n🗑️  Brokers duplicados a eliminar ({len(duplicates)}):")
        for broker in duplicates:
            # Contar cuentas asociadas
            account_count = BrokerAccount.query.filter_by(broker_id=broker.id).count()
            print(f"  - ID {broker.id}: {broker.name} ({account_count} cuenta(s) asociada(s))")
        
        confirm = input("\n¿Deseas eliminar estos brokers duplicados? (s/n): ")
        if confirm.lower() == 's':
            # Primero, reasignar cuentas a brokers válidos
            for broker in duplicates:
                accounts = BrokerAccount.query.filter_by(broker_id=broker.id).all()
                
                if accounts:
                    # Determinar broker válido según el nombre del duplicado
                    if 'degiro' in broker.name.lower():
                        target_broker_id = 2  # DeGiro
                        target_name = "DeGiro"
                    elif 'ibkr' in broker.name.lower():
                        target_broker_id = 1  # IBKR
                        target_name = "IBKR"
                    else:
                        target_broker_id = 3  # Manual
                        target_name = "Manual"
                    
                    print(f"\n  🔄 Reasignando {len(accounts)} cuenta(s) de '{broker.name}' → '{target_name}'")
                    for account in accounts:
                        account.broker_id = target_broker_id
                
                # Borrar el broker duplicado
                db.session.delete(broker)
            
            # Commit todos los cambios
            db.session.commit()
            print("\n✅ Brokers duplicados eliminados y cuentas reasignadas correctamente")
        else:
            print("❌ Operación cancelada")
    else:
        print("\n✅ No hay brokers duplicados. Solo existen los 3 predefinidos (ID 1, 2, 3).")

