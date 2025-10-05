"""
Rutas principales de la aplicación
"""
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.routes import main_bp


@main_bp.route('/')
def index():
    """Página de inicio"""
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal (requiere login)"""
    return render_template('dashboard.html')


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'app': 'FollowUp',
        'version': '2.0.0'
    }, 200

