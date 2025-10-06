"""
Blueprints de la aplicación
"""
from flask import Blueprint

# Blueprint principal
main_bp = Blueprint('main', __name__)

from app.routes import main_routes
from app.routes.auth import auth_bp
from app.routes.expenses import expenses_bp
from app.routes.incomes import incomes_bp

