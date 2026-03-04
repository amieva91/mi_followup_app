"""
Paquete de rutas de portfolio.
Cada funcionalidad está en un módulo separado.
"""
# Importar sub-módulos para registrar sus rutas en portfolio_bp
from app.routes.portfolio import accounts
from app.routes.portfolio import currencies
from app.routes.portfolio import mappings
from app.routes.portfolio import performance
from app.routes.portfolio import api
from app.routes.portfolio import prices
from app.routes.portfolio import holdings
from app.routes.portfolio import dashboard
from app.routes.portfolio import transactions
from app.routes.portfolio import import_routes
from app.routes.portfolio import assets
from app.routes.portfolio import watchlist
