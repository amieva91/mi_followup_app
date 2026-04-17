"""
Planificación de gastos / presupuestos (rama experimentos).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.services import spending_plan_service as sps

spending_plan_bp = Blueprint("spending_plan", __name__, url_prefix="/planificacion")


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
