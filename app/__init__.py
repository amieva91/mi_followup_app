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
    from app.routes.spending_plan import spending_plan_bp

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
    app.register_blueprint(spending_plan_bp)
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

    # Informes Deep Research: tras reinicio, reanudar polling si hay interaction_id (si no, fallar sin id)
    with app.app_context():
        try:
            from app.services.company_report_recovery import recover_processing_reports_after_restart

            recover_processing_reports_after_restart(app, app.logger)
        except Exception as ex:
            app.logger.warning('company_reports: recuperación al arranque omitida: %s', ex)

    # CLI: Job de polling de precios (ejecutar vía cron cada minuto)
    @app.cli.command('price-poll-one')
    def price_poll_one():
        """Actualiza 1 activo por rotación (Chart API solo). Ejecutar cada minuto vía cron."""
        import time

        from app.services.price_polling_service import run_poll_one

        t0 = time.perf_counter()
        # Sin exclusive_db_lock global: envolver run_poll_one bloqueaba todo el sitio web
        # durante la petición HTTP a Yahoo (flock EX compartido con Gunicorn).
        result = run_poll_one()
        elapsed = time.perf_counter() - t0
        if result and result.get("kind") == "asset":
            print(f"OK: actualizado asset_id={result.get('asset_id')} [cron price-poll-one {elapsed:.2f}s]")
        elif result and result.get("kind") == "benchmark":
            print(
                f"OK: actualizado benchmark {result.get('name')} ({result.get('ticker')}) "
                f"[cron price-poll-one {elapsed:.2f}s]"
            )
        else:
            print(f"OK: sin cola o sin actualización [cron price-poll-one {elapsed:.2f}s]")

    @app.cli.command('benchmark-global-daily-once')
    def benchmark_global_daily_once():
        """
        Mantiene series diarias globales de benchmarks (Yahoo si hace falta nuevo día).
        Ejecutar vía cron (p. ej. cada 15 min) con flock en la línea cron.
        """
        import time

        from app.services.benchmark_global_service import BenchmarkGlobalService

        t0 = time.perf_counter()
        ok = BenchmarkGlobalService.refresh_daily_if_stale()
        elapsed = time.perf_counter() - t0
        if ok:
            print(
                f"OK: benchmark global daily actualizado (versión {BenchmarkGlobalService.get_daily_data_version()}) "
                f"[{elapsed:.2f}s]"
            )
        else:
            print(f"OK: benchmark global daily sin cambios [{elapsed:.2f}s]")

    @app.cli.command('cache-rebuild-worker-once')
    def cache_rebuild_worker_once():
        """
        Procesa como máximo 1 usuario pendiente por ejecución (FULL domina NOW).
        Diseñado para cron cada ~30s con lock global para evitar solapes.
        """
        import os
        from datetime import datetime

        from flask import current_app

        from app.services.cache_rebuild_state_service import CacheRebuildStateService
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService
        from app.services.metrics.cache import MetricsCacheService
        from app.services.net_worth_service import get_dashboard_summary
        from app.services.portfolio_benchmarks_cache import PortfolioBenchmarksCacheService
        from app.services.portfolio_evolution_cache import PortfolioEvolutionCacheService

        import time

        t0 = time.perf_counter()

        def _elapsed_s() -> float:
            return time.perf_counter() - t0

        try:
            import fcntl
        except ImportError:
            click.echo(f'SKIP: fcntl no disponible para lock del worker. [cron cache-rebuild {_elapsed_s():.2f}s]')
            return

        os.makedirs(current_app.instance_path, exist_ok=True)
        lock_path = os.path.join(current_app.instance_path, 'cache_rebuild_worker.lock')
        fp = open(lock_path, 'a+')
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            click.echo(f'SKIP: worker ya en ejecución. [cron cache-rebuild {_elapsed_s():.2f}s]')
            fp.close()
            return

        try:
            row = CacheRebuildStateService.pick_next_pending()
            if not row:
                click.echo(f'OK: sin rebuild pendiente. [cron cache-rebuild {_elapsed_s():.2f}s]')
                return

            user_id = row.user_id
            action = 'full' if row.pending_full_history else 'now'
            started = datetime.utcnow()

            if action == 'full':
                # FULL: invalidar métricas y reconstruir snapshots completos.
                MetricsCacheService.invalidate(user_id)
                DashboardSummaryCacheService.set(user_id, get_dashboard_summary(user_id))
                # Fuerza snapshot mensual completo para performance/index comparison.
                PortfolioEvolutionCacheService.get_state(user_id, frequency='monthly')
                PortfolioBenchmarksCacheService.get_comparison_state(user_id)
            else:
                # NOW: conservar histórico, recalcular tramo actual.
                MetricsCacheService.invalidate(user_id)
                updated = DashboardSummaryCacheService.recompute_current_from_cache(user_id)
                if updated is None:
                    DashboardSummaryCacheService.set(user_id, get_dashboard_summary(user_id))
                PortfolioEvolutionCacheService.get_state(user_id, frequency='monthly')
                PortfolioBenchmarksCacheService.get_comparison_state(user_id)

            CacheRebuildStateService.clear_after_success(user_id, action=action)
            elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            total_s = _elapsed_s()
            click.echo(
                f'OK: rebuild {action} user_id={user_id} (trabajo {elapsed_ms} ms, total cron {total_s:.2f}s)'
            )
        finally:
            try:
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                fp.close()
            except Exception:
                pass

    @app.cli.command('reconciliation-debug')
    @click.option('--email', required=True, help='Email del usuario (ej. amieva91@gmail.com)')
    @click.option('--year', type=int, required=True)
    @click.option('--month', 'months', type=int, multiple=True, required=True, help='Mes(es), repetible: --month 2 --month 3')
    @click.option('--rows', is_flag=True, help='Listar filas de ingresos/gastos del mes')
    def reconciliation_debug(email, year, months, rows):
        """
        Desglose de reconciliación bancaria (cash + ingresos/gastos + broker) por mes.
        Ejecutar en el servidor donde esté la BD real:
        flask reconciliation-debug --email user@example.com --year 2026 --month 2 --month 3 --rows
        """
        from datetime import date as date_cls
        from sqlalchemy import extract

        from app.models import User, Income, Expense, IncomeCategory, ExpenseCategory, Transaction
        from app.services.bank_service import BankService
        from app.services.broker_sync_service import (
            get_broker_deposits_total_by_month,
            get_broker_withdrawals_by_month,
        )
        from app.services.reconciliation_service import (
            _get_prev_month,
            _month_range,
            _reconciliation_excluded_expense_category_ids,
            _reconciliation_excluded_income_category_ids,
            get_adjustment_for_month,
            get_expense_total_for_month,
            get_income_total_for_month,
        )
        from app.services.broker_sync_service import _broker_account_ids
        from app.services.currency_service import convert_to_eur

        user = User.query.filter_by(email=email.strip()).first()
        if not user:
            click.echo(f'No existe usuario con email {email!r}.', err=True)
            return
        uid = user.id
        click.echo(f'Usuario id={uid} email={user.email!r}\n')

        for month in months:
            if month < 1 or month > 12:
                click.echo(f'Mes inválido: {month}', err=True)
                continue
            py, pm = _get_prev_month(year, month)
            cash_prev = BankService.get_total_cash_by_month(uid, py, pm)
            cash_cur = BankService.get_total_cash_by_month(uid, year, month)
            start, end = _month_range(year, month)
            today = date_cls.today()
            inc_raw = float(Income.get_total_by_period(uid, start, end) or 0)
            exp_raw_q = db.session.query(db.func.sum(Expense.amount)).filter(
                Expense.user_id == uid,
                Expense.date >= start,
                Expense.date <= end,
                db.or_(
                    Expense.debt_plan_id.is_(None),
                    Expense.date <= today,
                ),
            )
            exp_raw = float(exp_raw_q.scalar() or 0)
            ex_i = _reconciliation_excluded_income_category_ids(uid)
            ex_e = _reconciliation_excluded_expense_category_ids(uid)
            inc_adj = get_income_total_for_month(uid, year, month)
            exp_adj = get_expense_total_for_month(uid, year, month)
            br_w = get_broker_withdrawals_by_month(uid, year, month)
            br_d = get_broker_deposits_total_by_month(uid, year, month)
            adj = get_adjustment_for_month(uid, year, month)
            real = cash_prev + inc_adj - cash_cur

            click.echo(f'=== {year}-{month:02d} (prev month cash {py}-{pm:02d}) ===')
            click.echo(f'  cash_prev (BankBalance):     {cash_prev:,.2f}')
            click.echo(f'  cash_current:                {cash_cur:,.2f}')
            click.echo(f'  incomes tabla (sin excl.):   {inc_raw:,.2f}  | categorías excl. ids: {ex_i}')
            click.echo(f'  + broker WITHDRAWAL:         {br_w:,.2f}')
            click.echo(f'  = ingresos (reconciliación): {inc_adj:,.2f}')
            click.echo(f'  gastos tabla (sin excl.):    {exp_raw:,.2f}  | categorías excl. ids: {ex_e}')
            click.echo(f'  + broker DEPOSIT:            {br_d:,.2f}')
            click.echo(f'  = gastos (reconciliación):   {exp_adj:,.2f}')
            click.echo(f'  gasto implícito (caja):      {real:,.2f}  (= prev + ing − cash)')
            click.echo(f'  ajuste (real − gastos reg.): {adj}')
            d_inc = inc_raw - (inc_adj - br_w)
            d_exp = exp_raw - (exp_adj - br_d)
            if abs(d_inc) > 0.005 or abs(d_exp) > 0.005:
                click.echo(
                    f'  → Diferencia por excl. Stock Market/Ajustes: '
                    f'ingresos tabla {d_inc:,.2f} €, gastos tabla {d_exp:,.2f} €'
                )
            click.echo('')

            if rows:
                incomes = (
                    Income.query.filter(
                        Income.user_id == uid,
                        Income.date >= start,
                        Income.date <= end,
                    )
                    .order_by(Income.date, Income.id)
                    .all()
                )
                click.echo(f'  Filas incomes ({len(incomes)}):')
                for r in incomes:
                    cat = db.session.get(IncomeCategory, r.category_id)
                    cname = cat.name if cat else '?'
                    desc = (r.description or '')[:60]
                    click.echo(
                        f'    {r.date} | {cname!r} | {r.amount:,.2f} | {desc!r}'
                    )
                exps = (
                    Expense.query.filter(
                        Expense.user_id == uid,
                        Expense.date >= start,
                        Expense.date <= end,
                        db.or_(
                            Expense.debt_plan_id.is_(None),
                            Expense.date <= today,
                        ),
                    )
                    .order_by(Expense.date, Expense.id)
                    .all()
                )
                click.echo(f'  Filas expenses ({len(exps)}):')
                for r in exps:
                    cat = db.session.get(ExpenseCategory, r.category_id)
                    cname = cat.name if cat else '?'
                    desc = (r.description or '')[:60]
                    click.echo(
                        f'    {r.date} | {cname!r} | {r.amount:,.2f} | {desc!r}'
                    )
                acc_ids = [x[0] for x in _broker_account_ids(uid)]
                if acc_ids:
                    w_tx = (
                        Transaction.query.filter(
                            Transaction.user_id == uid,
                            Transaction.account_id.in_(acc_ids),
                            Transaction.transaction_type == 'WITHDRAWAL',
                            extract('year', Transaction.transaction_date) == year,
                            extract('month', Transaction.transaction_date) == month,
                        )
                        .order_by(Transaction.transaction_date, Transaction.id)
                        .all()
                    )
                    click.echo(f'  WITHDRAWAL broker ({len(w_tx)}):')
                    for t in w_tx:
                        eur = convert_to_eur(abs(t.amount), t.currency)
                        click.echo(
                            f'    {t.transaction_date} | {eur:,.2f} EUR | id={t.id} amt={t.amount} {t.currency}'
                        )
                click.echo('')

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
