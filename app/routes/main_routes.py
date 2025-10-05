"""
Rutas principales de la aplicación
"""
from flask import render_template
from app.routes import main_bp


@main_bp.route('/')
def index():
    """Página de inicio"""
    return render_template('index.html')


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'app': 'FollowUp',
        'version': '2.0.0'
    }, 200

