"""
Rutas principales de la aplicación
"""
from flask import render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import func, extract
from app.routes import main_bp
from app import db
from app.models import Expense, Income, UserDashboardConfig, DEFAULT_WIDGETS
from app.services.net_worth_service import get_dashboard_summary


@main_bp.route('/')
def index():
    """Página de inicio"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con resumen de patrimonio"""
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService
    summary = DashboardSummaryCacheService.get(current_user.id)
    if summary is None:
        summary = get_dashboard_summary(current_user.id)
        DashboardSummaryCacheService.set(current_user.id, summary)
    
    # Obtener configuración de widgets del usuario
    widget_config = UserDashboardConfig.get_user_config(current_user.id)
    enabled_widgets = UserDashboardConfig.get_enabled_widgets(current_user.id)
    
    # Datos adicionales para widgets específicos
    now = datetime.now()
    
    return render_template(
        'dashboard.html',
        summary=summary,
        widget_config=widget_config,
        enabled_widgets=enabled_widgets,
        default_widgets=DEFAULT_WIDGETS,
        current_month_name=now.strftime('%B'),
        current_year=now.year
    )


@main_bp.route('/dashboard/config', methods=['POST'])
@login_required
def save_dashboard_config():
    """Guardar configuración de widgets del dashboard"""
    data = request.get_json()
    
    if not data or 'widgets' not in data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    widgets = data['widgets']
    UserDashboardConfig.save_user_config(current_user.id, widgets)
    
    return jsonify({'success': True, 'message': 'Configuración guardada'})


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'app': 'FollowUp',
        'version': '9.1.0'
    }, 200
