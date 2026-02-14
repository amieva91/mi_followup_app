"""
Factory pattern para la aplicación FollowUp
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from config import config

# Extensiones (se inicializan sin app)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_name='default'):
    """Factory para crear la aplicación"""
    app = Flask(__name__)
    
    # Configurar logging
    import logging
    from logging.handlers import RotatingFileHandler
    import os
    
    # Crear directorio de logs si no existe
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configurar handler para archivo (solo en producción)
    if config_name == 'production':
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'followup.log'),
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
    
    # Configurar logging básico (consola)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.setLevel(logging.INFO)
    
    # Cargar configuración
    app.config.from_object(config[config_name])
    
    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    
    # Configurar Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify, redirect, url_for
        # Para rutas API, devolver JSON en lugar de redirect (evita "is not valid JSON")
        if request.path.startswith('/portfolio/api/'):
            return jsonify({'success': False, 'error': 'Sesión expirada. Recarga la página.'}), 401
        return redirect(url_for(login_manager.login_view))
    
    # User loader para Flask-Login
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Registrar filtros personalizados para templates
    from app.utils.template_filters import register_filters
    register_filters(app)
    
    # Context processor para CSRF token global
    # Flask-WTF ya proporciona csrf_token() automáticamente, pero lo aseguramos aquí
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    
    # Registrar blueprints
    from app.routes import main_bp, portfolio_bp, debts_bp
    from app.routes.auth import auth_bp
    from app.routes.expenses import expenses_bp
    from app.routes.incomes import incomes_bp
    from app.routes.crypto import crypto_bp
    from app.routes.metales import metales_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(incomes_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(crypto_bp)
    app.register_blueprint(metales_bp)

    # Para rutas API: devolver JSON en 404/500 (evita "is not valid JSON" en frontend)
    @app.errorhandler(404)
    def not_found_handler(e):
        from flask import request, jsonify
        # Cualquier ruta que parezca API debe devolver JSON
        if '/api/' in request.path or request.path.endswith('/api/report-templates') or 'report-templates' in request.path:
            return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404
        return '<h1>Página no encontrada</h1>', 404

    @app.errorhandler(500)
    def server_error_handler(e):
        from flask import request, jsonify
        if '/api/' in request.path or 'report-templates' in request.path:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
        return '<h1>Error interno</h1>', 500
    
    # Crear carpetas necesarias
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['OUTPUT_FOLDER'], 'reports_audio'), exist_ok=True)
    os.makedirs(app.root_path + '/../instance', exist_ok=True)
    
    return app
