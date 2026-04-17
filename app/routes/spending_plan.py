"""
Planificación de gastos / presupuestos (rama experimentos).
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.services import spending_plan_service as sps

spending_plan_bp = Blueprint("spending_plan", __name__, url_prefix="/planificacion")


def _parse_target_date(raw: str):
    if not raw or not str(raw).strip():
        return None
    try:
        return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


@spending_plan_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not token:
            flash("Sesión expirada. Recarga la página.", "error")
            return redirect(url_for("spending_plan.index"))
        try:
            max_dsr = float(request.form.get("max_dsr_percent") or 35)
            horizon = int(request.form.get("horizon_months") or 12)
            raw = request.form.getlist("fixed_category_ids")
            cat_ids = [int(x) for x in raw if str(x).strip().isdigit()]
            sps.update_settings(current_user.id, max_dsr, horizon)
            sps.set_fixed_categories(current_user.id, cat_ids)
            flash("Configuración guardada.", "success")
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            db.session.rollback()
            flash(f"No se pudo guardar: {e}", "error")
        return redirect(url_for("spending_plan.index"))

    data = sps.get_spending_plan_page_data(current_user.id)
    return render_template("spending_plan/index.html", **data)


@spending_plan_bp.route("/objetivo", methods=["POST"])
@login_required
def add_goal():
    if not request.form.get("csrf_token"):
        flash("Sesión expirada.", "error")
        return redirect(url_for("spending_plan.index"))
    try:
        title = request.form.get("title") or ""
        amount = float(request.form.get("amount_total") or 0)
        priority = int(request.form.get("priority") or 3)
        td = _parse_target_date(request.form.get("target_date") or "")
        gtype = (request.form.get("goal_type") or "generic").strip().lower()
        sps.add_goal(current_user.id, title, amount, priority, td, gtype)
        flash("Objetivo añadido.", "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo añadir: {e}", "error")
    return redirect(url_for("spending_plan.index"))


@spending_plan_bp.route("/objetivo/<int:goal_id>/eliminar", methods=["POST"])
@login_required
def delete_goal(goal_id: int):
    if not request.form.get("csrf_token"):
        flash("Sesión expirada.", "error")
        return redirect(url_for("spending_plan.index"))
    if sps.delete_goal(current_user.id, goal_id):
        flash("Objetivo eliminado.", "success")
    else:
        flash("Objetivo no encontrado.", "error")
    return redirect(url_for("spending_plan.index"))
