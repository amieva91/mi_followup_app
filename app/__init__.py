"""
Factory pattern para la aplicación FollowUp
"""
import click
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

_SQLITE_PRAGMAS_REGISTERED = False


def _register_sqlite_concurrency_pragmas():
    """
    WAL + busy_timeout en SQLite para reducir 'database is locked' cuando
    coinciden el servidor Flask y el cron (flask price-poll-one).
    """
    global _SQLITE_PRAGMAS_REGISTERED
    if _SQLITE_PRAGMAS_REGISTERED:
        return
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _sqlite_on_connect(dbapi_connection, connection_record):
        import sqlite3

        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        try:
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=60000")
            cur.close()
        except Exception:
            pass

    _SQLITE_PRAGMAS_REGISTERED = True


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
    
    # Configurar handler para archivo (desarrollo y producción) para que Admin → Sistema pueda mostrar logs
    try:
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
    except (PermissionError, OSError):
        pass  # Fallback a solo consola si no hay permisos
    
    # Configurar logging básico (consola)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.setLevel(logging.INFO)
    
    # Cargar configuración
    app.config.from_object(config[config_name])

    _register_sqlite_concurrency_pragmas()

    # Inicializar extensiones
    db.init_app(app)
    from app.sqlite_cross_process_lock import register_sqlite_cross_process_lock

    register_sqlite_cross_process_lock(app, db)
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
    from app.routes.banks import banks_bp
    from app.routes.crypto import crypto_bp
    from app.routes.metales import metales_bp
    from app.routes.real_estate import real_estate_bp
    from app.routes.admin_routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(incomes_bp)
    app.register_blueprint(banks_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(crypto_bp)
    app.register_blueprint(metales_bp)
    app.register_blueprint(real_estate_bp)
    app.register_blueprint(admin_bp)

    # Log de cada petición al archivo (visible en Admin → Sistema → Logs de la aplicación)
    @app.after_request
    def log_request(response):
        from flask import request
        from flask_login import current_user
        user = current_user.username if current_user.is_authenticated else '-'
        app.logger.info(
            "%s %s %s → %s",
            request.method,
            request.path,
            user,
            response.status_code,
        )
        return response

    # Obligar cambio de contraseña en primer inicio
    @app.before_request
    def require_change_password_if_needed():
        from flask import request, redirect, url_for
        from flask_login import current_user
        from app.models import User
        if not current_user.is_authenticated:
            return
        user = User.query.get(current_user.id)
        if not user or not getattr(user, 'must_change_password', False):
            return
        if request.endpoint in ('auth.must_change_password', 'auth.logout'):
            return
        if request.blueprint == 'static':
            return
        return redirect(url_for('auth.must_change_password'))

    # Cuenta administrador: solo puede ver rutas de /admin, catálogos (asset-registry, mappings) y logout
    @app.before_request
    def administrador_only_admin_routes():
        from flask import request, redirect, url_for
        from flask_login import current_user
        if not current_user.is_authenticated:
            return
        if getattr(current_user, 'username', None) != 'administrador':
            return
        if request.blueprint == 'admin':
            return
        if request.endpoint in ('auth.logout', 'auth.must_change_password'):
            return
        if request.blueprint == 'static':
            return
        if request.path.startswith('/portfolio/asset-registry') or request.path.startswith('/portfolio/mappings'):
            return
        return redirect(url_for('admin.index'))

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

    # CLI: Job de polling de precios (ejecutar vía cron cada minuto)
    @app.cli.command('price-poll-one')
    def price_poll_one():
        """Actualiza 1 activo por rotación (Chart API solo). Ejecutar cada minuto vía cron."""
        from flask import current_app

        from app.sqlite_cross_process_lock import exclusive_db_lock
        from app.services.price_polling_service import run_poll_one

        with exclusive_db_lock(current_app):
            asset_id = run_poll_one()
        if asset_id:
            print(f"OK: actualizado asset_id={asset_id}")
        else:
            print("OK: sin activos o sin actualización")

    @app.cli.command('price-flash-test')
    @click.option('--user-id', type=int, default=None)
    @click.option('--index', type=int, default=0, help='Posición en Top Movers: 0=primero, 1=segundo, …')
    def price_flash_test(user_id, index):
        """Solo pruebas: marca last_price_update=ahora en un Top Mover para disparar el flash."""
        from datetime import datetime
        from flask import current_app

        from app.models import User
        from app.models.asset import Asset
        from app.services.net_worth_service import get_top_movers_for_user
        from app.sqlite_cross_process_lock import exclusive_db_lock

        with exclusive_db_lock(current_app):
            uid = user_id or (User.query.filter(User.username != 'administrador').first() or User.query.first())
            if not uid:
                click.echo('No hay usuarios.', err=True)
                return
            uid = uid.id if hasattr(uid, 'id') else uid
            movers = get_top_movers_for_user(uid, limit=5)
            if not movers or index < 0 or index >= len(movers):
                click.echo(f'Sin Top Movers o index inválido (0–{len(movers)-1}).', err=True)
                return
            aid = movers[index]['asset_id']
            asset = db.session.get(Asset, aid)
            if not asset:
                click.echo(f'Asset id={aid} no encontrado.', err=True)
                return
            asset.last_price_update = datetime.utcnow()
            db.session.commit()
        click.echo(f'OK: last_price_update=now para Top Movers[{index}] → {asset.symbol} (id={aid}). Espera ≤30s.')

    @app.cli.command('price-simulate-change')
    @click.option('--user-id', type=int, default=None)
    @click.option('--bump', type=float, default=0.001, help='Incremento relativo del precio (0.001 = +0.1%%)')
    @click.option('--scope', type=click.Choice(['top_movers', 'all']), default='top_movers',
                  help='top_movers: solo los 5 primeros; all: holdings + watchlist')
    def price_simulate_change(user_id, bump, scope):
        """
        Solo pruebas: cambia current_price de activos (holdings + watchlist) para ver
        actualización en vivo. Ejecuta, deja /dashboard o /portfolio abiertos, espera ≤30s.
        Usa "Actualizar precios" manual para restaurar valores reales.
        """
        from datetime import datetime
        from flask import current_app

        from app.models import User
        from app.models.asset import Asset
        from app.services.net_worth_service import get_top_movers_for_user
        from app.sqlite_cross_process_lock import exclusive_db_lock

        with exclusive_db_lock(current_app):
            uid = user_id or (User.query.filter(User.username != 'administrador').first() or User.query.first())
            if not uid:
                click.echo('No hay usuarios.', err=True)
                return
            uid = uid.id if hasattr(uid, 'id') else uid
            if scope == 'top_movers':
                movers = get_top_movers_for_user(uid, limit=5)
                asset_ids = [m['asset_id'] for m in movers] if movers else []
            else:
                from app.models.portfolio import PortfolioHolding
                from app.models.watchlist import Watchlist
                holding_ids = {r[0] for r in db.session.query(PortfolioHolding.asset_id)
                              .filter(PortfolioHolding.user_id == uid, PortfolioHolding.quantity > 0).distinct().all()}
                watch_ids = {r[0] for r in db.session.query(Watchlist.asset_id).filter(Watchlist.user_id == uid).distinct().all()}
                asset_ids = list(holding_ids | watch_ids)
            if not asset_ids:
                click.echo('Sin activos para modificar.', err=True)
                return
            count = 0
            for aid in asset_ids:
                a = db.session.get(Asset, aid)
                if not a or not a.current_price or a.current_price <= 0:
                    continue
                a.current_price = round(a.current_price * (1 + bump), 6)
                if a.previous_close and a.previous_close > 0:
                    a.day_change_percent = round((a.current_price - a.previous_close) / a.previous_close * 100, 2)
                a.last_price_update = datetime.utcnow()
                count += 1
            db.session.commit()
        click.echo(
            f'OK: {count} activos con precio ×(1+{bump}). '
            f'Deja /dashboard o /portfolio abiertos, espera ≤30s para ver cambios + flash.'
        )

    @app.cli.command('reset-pollable-prices-demo')
    @click.option('--yes', '-y', is_flag=True, help='Confirmar sin preguntar (obligatorio en scripts)')
    def reset_pollable_prices_demo(yes):
        """
        Demo: borra precio/cierre/% día en activos que actualiza el cron; reinicia índice de rotación;
        elimina caches de dashboard, evolution, benchmarks y métricas para ver cómo se repueblan.
        """
        from flask import current_app

        from app.models.dashboard_summary_cache import DashboardSummaryCache
        from app.models.metrics_cache import MetricsCache
        from app.models.portfolio_benchmarks_cache import PortfolioBenchmarksCache
        from app.models.portfolio_evolution_cache import PortfolioEvolutionCache
        from app.models.price_polling_state import PricePollingState
        from app.services.price_polling_service import get_assets_to_poll
        from app.sqlite_cross_process_lock import exclusive_db_lock

        if not yes:
            click.confirm(
                'Se borrarán precios Yahoo en activos del job de polling y TODAS las filas de '
                'caches (dashboard, evolution, benchmarks, métricas). ¿Continuar?',
                abort=True,
            )

        with exclusive_db_lock(current_app):
            assets = get_assets_to_poll()
            for a in assets:
                a.current_price = None
                a.previous_close = None
                a.day_change_percent = None
                a.last_price_update = None
                a.last_price = None
            db.session.commit()
            n_assets = len(assets)

            st = db.session.get(PricePollingState, 1)
            if st:
                st.last_asset_index = -1
                st.last_updated_asset_id = None
            else:
                db.session.add(
                    PricePollingState(id=1, last_asset_index=-1, last_updated_asset_id=None)
                )
            db.session.commit()

            DashboardSummaryCache.query.delete(synchronize_session=False)
            PortfolioEvolutionCache.query.delete(synchronize_session=False)
            PortfolioBenchmarksCache.query.delete(synchronize_session=False)
            MetricsCache.query.delete(synchronize_session=False)
            db.session.commit()

        click.echo(
            f'OK: {n_assets} activos sin precio; rotación reiniciada; caches de dashboard/métricas/evolution/benchmarks vaciadas.'
        )

    return app
