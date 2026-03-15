"""
Panel de administración: solo accesible para usuarios con is_admin=True.
"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from app import db
from app.models import (
    User,
    MODULES,
    AssetRegistry,
    AssetDelisting,
    MappingRegistry,
    MetricsCache,
    DashboardSummaryCache,
    UserLoginLog,
)
from app.services.admin_user_service import delete_user_and_data
from app.services.api_log_service import get_api_metrics, log_api_call
from app.services.metrics.cache import MetricsCacheService
from app.services.dashboard_summary_cache import DashboardSummaryCacheService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator: exige login y is_admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "is_admin", False):
            flash("No tienes permiso para acceder al panel de administración.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@login_required
@admin_required
def index():
    """Dashboard del panel admin: enlaces a cada sección."""
    return render_template("admin/index.html")


# ---------- Usuarios ----------
@admin_bp.route("/users")
@login_required
@admin_required
def users_list():
    """Listado de usuarios con acciones y registro de últimos logins."""
    users = User.query.order_by(User.id).all()
    recent_logins = (
        UserLoginLog.query.join(User)
        .order_by(UserLoginLog.logged_at.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "admin/users_list.html",
        users=users,
        modules=MODULES,
        recent_logins=recent_logins,
    )


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def user_toggle_active(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("No puedes desactivar tu propia cuenta.", "error")
        return redirect(url_for("admin.users_list"))
    if u.is_admin:
        flash("No puedes desactivar a un administrador.", "error")
        return redirect(url_for("admin.users_list"))
    u.is_active = not u.is_active
    db.session.commit()
    flash(f"Usuario {u.username} {'activado' if u.is_active else 'desactivado'}.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def user_toggle_admin(user_id):
    u = User.query.get_or_404(user_id)
    # Solo el usuario con username 'administrador' puede ser admin; no se puede quitar ni dar a otros
    if u.username == "administrador":
        flash("El usuario administrador debe conservar siempre el rol de administrador.", "error")
        return redirect(url_for("admin.users_list"))
    if not u.is_admin:
        # Estaríamos dando admin a otro usuario: no permitido
        flash("Solo el usuario 'administrador' puede ser administrador. No se puede dar este rol a otros usuarios.", "error")
        return redirect(url_for("admin.users_list"))
    # Quitar admin a alguien que no sea 'administrador'
    u.is_admin = False
    db.session.commit()
    flash(f"Rol de administrador quitado a {u.username}. Solo el usuario 'administrador' puede ser admin.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/edit-modules", methods=["GET", "POST"])
@login_required
@admin_required
def user_edit_modules(user_id):
    u = User.query.get_or_404(user_id)
    if u.username == "administrador":
        flash("El usuario administrador no tiene módulos configurables.", "info")
        return redirect(url_for("admin.users_list"))
    if request.method == "POST":
        enabled = request.form.getlist("modules")
        u.enabled_modules = enabled if enabled else None
        db.session.commit()
        flash(f"Módulos de {u.username} actualizados.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_edit_modules.html", user=u, modules=MODULES)


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@admin_required
def user_reset_password_form(user_id):
    u = User.query.get_or_404(user_id)
    if request.method == "GET":
        return render_template("admin/user_reset_password.html", user=u)
    new_password = request.form.get("new_password", "").strip()
    if not new_password or len(new_password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "error")
        return redirect(url_for("admin.user_reset_password_form", user_id=user_id))
    u.set_password(new_password)
    db.session.commit()
    flash(f"Contraseña de {u.username} actualizada.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/delete-confirm")
@login_required
@admin_required
def user_delete_confirm(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("No puedes eliminarte a ti mismo.", "error")
        return redirect(url_for("admin.users_list"))
    if u.username == "administrador":
        flash("No se puede eliminar el usuario administrador fijo.", "error")
        return redirect(url_for("admin.users_list"))
    if u.is_admin:
        flash("No se puede eliminar un usuario administrador.", "error")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_delete_confirm.html", user=u)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("No puedes eliminarte a ti mismo.", "error")
        return redirect(url_for("admin.users_list"))
    if u.is_admin:
        flash("No se puede eliminar un usuario administrador.", "error")
        return redirect(url_for("admin.users_list"))
    if u.username == "administrador":
        flash("No se puede eliminar el usuario administrador fijo.", "error")
        return redirect(url_for("admin.users_list"))
    confirm = request.form.get("confirm") == "yes"
    if not confirm:
        flash("Debes confirmar la eliminación (marca la casilla).", "error")
        return redirect(url_for("admin.users_list"))
    success, msg = delete_user_and_data(user_id)
    if success:
        flash(msg, "success")
    else:
        flash(f"Error: {msg}", "error")
    return redirect(url_for("admin.users_list"))


# ---------- Monitor API ----------
@admin_bp.route("/api-monitor")
@login_required
@admin_required
def api_monitor():
    """Listado de llamadas a APIs con filtros (fecha, status, api, endpoint, usuario) y retención 6 meses."""
    from app.services.api_log_service import (
        get_api_metrics,
        get_api_logs_filtered,
        get_api_names_distinct,
        delete_logs_older_than_retention,
        get_api_calls_chart_data,
    )
    from datetime import datetime as dt
    from app.models import ApiCallLog

    delete_logs_older_than_retention(months=6)

    days = request.args.get("days", type=int, default=30)
    if days < 1 or days > 365:
        days = 30
    metrics = get_api_metrics(days=days)

    date_from_s = request.args.get("date_from")
    date_to_s = request.args.get("date_to")
    date_from = None
    date_to = None
    try:
        if date_from_s:
            date_from = dt.strptime(date_from_s, "%Y-%m-%d").date()
        if date_to_s:
            date_to = dt.strptime(date_to_s, "%Y-%m-%d").date()
    except ValueError:
        date_from_s = date_to_s = None
    status = request.args.get("status") or None
    api_name = request.args.get("api_name") or None
    endpoint = request.args.get("endpoint", "").strip() or None
    user_id = request.args.get("user_id", type=int)
    if user_id is not None and user_id <= 0:
        user_id = None

    recent = get_api_logs_filtered(
        date_from=date_from,
        date_to=date_to,
        status=status,
        api_name=api_name,
        endpoint_substring=endpoint,
        user_id=user_id,
        limit=500,
    )
    api_names = get_api_names_distinct()
    users_for_filter = User.query.order_by(User.username).all()
    user_names = {u.id: u.username for u in users_for_filter}
    chart_data = get_api_calls_chart_data(days=days)

    return render_template(
        "admin/api_monitor.html",
        metrics=metrics,
        recent=recent,
        days=days,
        date_from=date_from_s,
        date_to=date_to_s,
        status=status,
        api_name=api_name,
        endpoint=request.args.get("endpoint", ""),
        user_id=user_id,
        api_names=api_names,
        users_for_filter=users_for_filter,
        user_names=user_names,
        chart_data=chart_data,
    )


# ---------- Catálogos ----------
@admin_bp.route("/catalogs")
@login_required
@admin_required
def catalogs():
    """Enlaces a AssetRegistry, AssetDelisting, MappingRegistry (listados/edición)."""
    registry_count = AssetRegistry.query.count()
    delisting_count = AssetDelisting.query.count()
    mapping_count = MappingRegistry.query.count()
    return render_template(
        "admin/catalogs.html",
        registry_count=registry_count,
        delisting_count=delisting_count,
        mapping_count=mapping_count,
    )


@admin_bp.route("/catalogs/registry")
@login_required
@admin_required
def catalog_registry():
    """Listado del registro de activos (solo lectura o enlace a la vista existente)."""
    return redirect(url_for("portfolio.asset_registry"))


# ---------- Cache ----------
@admin_bp.route("/cache", methods=["GET", "POST"])
@login_required
@admin_required
def cache():
    """Invalidar cache de métricas y dashboard (por usuario o todo)."""
    if request.method == "POST":
        # "Invalidar todo" no envía user_id
        user_id = request.form.get("user_id", type=int) if request.form.get("user_id") else None
        if user_id:
            MetricsCacheService.invalidate(user_id)
            DashboardSummaryCacheService.invalidate(user_id)
            flash(f"Cache invalidado para el usuario {user_id}.", "success")
        else:
            for c in MetricsCache.query.all():
                db.session.delete(c)
            for c in DashboardSummaryCache.query.all():
                db.session.delete(c)
            db.session.commit()
            flash("Cache invalidado para todos los usuarios.", "success")
        return redirect(url_for("admin.cache"))
    users = User.query.order_by(User.username).all()
    return render_template("admin/cache.html", users=users)


# ---------- Sistema ----------
def _read_log_tail(path: str, max_lines: int = 1000, max_bytes: int = 512 * 1024) -> tuple[list[str] | None, str | None]:
    """Lee las últimas líneas del archivo de log. Devuelve (list de líneas, None) o (None, mensaje de error)."""
    import os
    if not path or not os.path.isfile(path):
        return None, "No existe el archivo de log."
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size <= max_bytes:
                f.seek(0)
                data = f.read()
            else:
                f.seek(size - max_bytes)
                data = f.read()
        text = data.decode("utf-8", errors="replace")
        lines = [line for line in text.splitlines()]
        return lines[-max_lines:] if len(lines) > max_lines else lines, None
    except PermissionError:
        return None, "Sin permiso de lectura del archivo de log."
    except Exception as e:
        return None, str(e)


@admin_bp.route("/system")
@login_required
@admin_required
def system():
    """Resumen del sistema: nº usuarios, logs de aplicación, etc."""
    from sqlalchemy import text
    user_count = User.query.count()
    try:
        result = db.session.execute(text("SELECT COUNT(*) FROM transactions"))
        tx_count = result.scalar() or 0
    except Exception:
        tx_count = 0
    try:
        result = db.session.execute(text("SELECT COUNT(*) FROM expense_categories"))
        exp_cat_count = result.scalar() or 0
    except Exception:
        exp_cat_count = 0

    log_path = current_app.config.get("LOG_FILE")
    log_lines, log_error = _read_log_tail(log_path) if log_path else (None, "LOG_FILE no configurado.")

    return render_template(
        "admin/system.html",
        user_count=user_count,
        tx_count=tx_count,
        exp_cat_count=exp_cat_count,
        log_lines=log_lines,
        log_error=log_error,
        log_path=log_path,
    )
