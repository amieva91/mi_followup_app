"""
Blueprints de la aplicación
"""
from flask import Blueprint

# Blueprint principal
main_bp = Blueprint('main', __name__)

from app.routes import main_routes

