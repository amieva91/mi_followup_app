"""
Seed para módulo Metales - Crea broker Commodities y assets de metales preciosos.
Tickers Yahoo (futuros USD): GC=F (Oro), SI=F (Plata), PL=F (Platino), PA=F (Paladio)

Ejecutar desde la raíz del proyecto:
  python -c "from app import create_app; from app import db; app = create_app(); app.app_context().push(); exec(open('docs/scripts/seed_metales.py').read())"
"""
from app import db
from app.models import Broker, Asset

METALS = [
    {'symbol': 'GC=F', 'name': 'Oro (XAU)', 'yahoo_ticker': 'GC=F'},
    {'symbol': 'SI=F', 'name': 'Plata (XAG)', 'yahoo_ticker': 'SI=F'},
    {'symbol': 'PL=F', 'name': 'Platino (XPT)', 'yahoo_ticker': 'PL=F'},
    {'symbol': 'PA=F', 'name': 'Paladio (XPD)', 'yahoo_ticker': 'PA=F'},
]

def run():
    # 1. Broker Commodities
    broker = Broker.query.filter(Broker.name.ilike('%commodit%')).first()
    if not broker:
        broker = Broker(name='Commodities', full_name='Metales físicos')
        db.session.add(broker)
        db.session.flush()
        print('✅ Broker "Commodities" creado')
    else:
        print('⏭️  Broker Commodities ya existe')

    # 2. Assets de metales
    for m in METALS:
        existing = Asset.query.filter(Asset.symbol == m['symbol'], Asset.asset_type == 'Commodity').first()
        if not existing:
            asset = Asset(
                symbol=m['symbol'],
                name=m['name'],
                asset_type='Commodity',
                currency='USD',
                yahoo_suffix='',  # symbol ya incluye =F para Yahoo
            )
            db.session.add(asset)
            print(f'✅ Asset creado: {m["symbol"]} ({m["name"]})')
        else:
            print(f'⏭️  Asset {m["symbol"]} ya existe')

    db.session.commit()
    print('\n✅ Seed metales completado')

run()
