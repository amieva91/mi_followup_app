"""
Script de test para probar la importación completa de CSV a BD
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import User, BrokerAccount, Broker, Asset, PortfolioHolding, Transaction
from app.services.csv_detector import detect_and_parse
from app.services.importer import CSVImporter


def test_import():
    """Prueba la importación completa de un CSV"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 80)
        print("TEST: Importación completa de CSV a Base de Datos")
        print("=" * 80)
        
        # 1. Buscar o crear usuario de test
        user = User.query.filter_by(email='test@test.com').first()
        if not user:
            user = User(
                username='testuser',
                email='test@test.com'
            )
            user.set_password('test123')
            db.session.add(user)
            db.session.commit()
            print(f"\n✅ Usuario de test creado: {user.email} (ID: {user.id})")
        else:
            print(f"\n✅ Usuario: {user.email} (ID: {user.id})")
        
        # 2. Buscar broker
        broker = Broker.query.filter_by(name='IBKR').first()
        if not broker:
            print("\n❌ Broker IBKR no encontrado. Ejecuta seed_brokers.py primero.")
            return
        
        print(f"✅ Broker: {broker.name}")
        
        # 3. Buscar o crear cuenta de test
        account = BrokerAccount.query.filter_by(
            user_id=user.id,
            broker_id=broker.id,
            account_name='Test IBKR Import'
        ).first()
        
        if not account:
            account = BrokerAccount(
                user_id=user.id,
                broker_id=broker.id,
                account_name='Test IBKR Import',
                account_number='TEST001',
                base_currency='EUR'
            )
            db.session.add(account)
            db.session.commit()
            print(f"\n✅ Cuenta creada: {account.account_name} (ID: {account.id})")
        else:
            print(f"\n✅ Cuenta existente: {account.account_name} (ID: {account.id})")
        
        # 4. Parsear CSV
        print("\n📄 Parseando CSV...")
        csv_file = 'uploads/IBKR.csv'
        
        if not os.path.exists(csv_file):
            print(f"❌ Archivo no encontrado: {csv_file}")
            return
        
        parsed_data = detect_and_parse(csv_file)
        print(f"✅ CSV parseado:")
        print(f"   - Trades: {len(parsed_data['trades'])}")
        print(f"   - Holdings: {len(parsed_data['holdings'])}")
        print(f"   - Dividends: {len(parsed_data['dividends'])}")
        
        # 5. Contar datos previos
        prev_assets = Asset.query.count()  # Assets son compartidos (catálogo global)
        prev_transactions = Transaction.query.filter_by(account_id=account.id).count()
        prev_holdings = PortfolioHolding.query.filter_by(account_id=account.id).count()
        
        print(f"\n📊 Estado previo en BD:")
        print(f"   - Assets (global): {prev_assets}")
        print(f"   - Transactions: {prev_transactions}")
        print(f"   - Holdings: {prev_holdings}")
        
        # 6. Importar
        print("\n🚀 Importando datos...")
        importer = CSVImporter(user_id=user.id, broker_account_id=account.id)
        stats = importer.import_data(parsed_data)
        
        print(f"\n✅ Importación completada:")
        print(f"   - Assets creados: {stats['assets_created']}")
        print(f"   - Assets actualizados: {stats['assets_updated']}")
        print(f"   - Transacciones creadas: {stats['transactions_created']}")
        print(f"   - Transacciones duplicadas (skip): {stats['transactions_skipped']}")
        print(f"   - Holdings creados: {stats['holdings_created']}")
        print(f"   - Holdings actualizados: {stats['holdings_updated']}")
        print(f"   - Dividendos creados: {stats['dividends_created']}")
        
        # 7. Verificar estado final
        final_assets = Asset.query.count()
        final_transactions = Transaction.query.filter_by(account_id=account.id).count()
        final_holdings = PortfolioHolding.query.filter_by(account_id=account.id).count()
        
        print(f"\n📊 Estado final en BD:")
        print(f"   - Assets (global): {final_assets} (+{final_assets - prev_assets})")
        print(f"   - Transactions: {final_transactions} (+{final_transactions - prev_transactions})")
        print(f"   - Holdings: {final_holdings} (+{final_holdings - prev_holdings})")
        
        # 8. Mostrar algunos holdings
        print(f"\n📈 Primeros 5 holdings:")
        holdings = PortfolioHolding.query.filter_by(account_id=account.id).limit(5).all()
        for h in holdings:
            print(f"   - {h.asset.symbol}: {h.quantity} @ {h.average_buy_price:.2f} {h.asset.currency}")
            print(f"     Total cost: {h.total_cost:.2f}")
        
        # 9. Test de duplicados (importar de nuevo)
        print(f"\n🔄 Test de duplicados (importando de nuevo)...")
        importer2 = CSVImporter(user_id=user.id, broker_account_id=account.id)
        stats2 = importer2.import_data(parsed_data)
        
        print(f"✅ Segunda importación:")
        print(f"   - Transacciones creadas: {stats2['transactions_created']}")
        print(f"   - Transacciones duplicadas (skip): {stats2['transactions_skipped']}")
        
        if stats2['transactions_created'] == 0 and stats2['transactions_skipped'] > 0:
            print(f"\n✅ ¡Detección de duplicados funcionando correctamente!")
        else:
            print(f"\n⚠️  Advertencia: Se crearon transacciones duplicadas")
        
        print("\n" + "=" * 80)
        print("✅ Test completado")
        print("=" * 80 + "\n")


if __name__ == '__main__':
    test_import()

