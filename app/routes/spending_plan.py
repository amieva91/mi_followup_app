"""
Planificación de gastos / presupuestos (rama experimentos).
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.services import spending_plan_service as sps
from app.services import mortgage_simulation_service as mss
from app.services import interest_rate_context_service as irctx

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
        extra = (request.form.get("extra_json") or "").strip() or None
        sps.add_goal(
            current_user.id, title, amount, priority, td, gtype, extra_json=extra
        )
        flash("Objetivo añadido.", "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo añadir: {e}", "error")
    return redirect(url_for("spending_plan.index"))


def _default_mortgage_form():
    return {
        "purchase_price": "280000",
        "savings": "32000",
        "years": "30",
        "first_home": True,
        "annual_interest_percent": "3.50",
        "notary": str(mss.DEFAULT_NOTARY),
        "registry": str(mss.DEFAULT_REGISTRY),
        "gestoria": str(mss.DEFAULT_GESTORIA),
        "tasacion": str(mss.DEFAULT_TASACION),
    }


@spending_plan_bp.route("/vivienda", methods=["GET", "POST"])
@login_required
def mortgage_simulator():
    result = None
    interest_context = irctx.get_latest_snapshot()
    sim_form = _default_mortgage_form()
    if interest_context and interest_context.bce_euribor_12m_percent is not None:
        sim_form["annual_interest_percent"] = (
            f"{float(interest_context.bce_euribor_12m_percent):.2f}"
        )

    if request.method == "POST" and request.form.get("action") == "simulate":
        if not request.form.get("csrf_token"):
            flash("Sesión expirada.", "error")
            return redirect(url_for("spending_plan.mortgage_simulator"))
        sim_form = {
            "purchase_price": (request.form.get("purchase_price") or "").strip(),
            "savings": (request.form.get("savings") or "").strip(),
            "years": (request.form.get("years") or "").strip(),
            "first_home": request.form.get("first_home") == "1",
            "annual_interest_percent": (
                request.form.get("annual_interest_percent") or ""
            ).strip(),
            "notary": (request.form.get("notary") or "").strip(),
            "registry": (request.form.get("registry") or "").strip(),
            "gestoria": (request.form.get("gestoria") or "").strip(),
            "tasacion": (request.form.get("tasacion") or "").strip(),
        }
        try:
            pp = float(sim_form["purchase_price"] or 0)
            sav = float(sim_form["savings"] or 0)
            yrs = int(sim_form["years"] or 30)
            first = sim_form["first_home"]
            annual = float(sim_form["annual_interest_percent"] or 3.5)
            notary = float(sim_form["notary"] or mss.DEFAULT_NOTARY)
            registry = float(sim_form["registry"] or mss.DEFAULT_REGISTRY)
            gestoria = float(sim_form["gestoria"] or mss.DEFAULT_GESTORIA)
            tasacion = float(sim_form["tasacion"] or mss.DEFAULT_TASACION)
            result = mss.run_simulation(
                purchase_price=pp,
                savings_cash=sav,
                years=yrs,
                first_home=first,
                notary=notary,
                registry=registry,
                gestoria=gestoria,
                tasacion_fee=tasacion,
                annual_interest_percent=annual,
            )
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"Simulación no disponible: {e}", "error")

    negotiation_hints = None
    if interest_context and interest_context.bce_euribor_12m_percent is not None:
        negotiation_hints = mss.fixed_rate_negotiation_hints(
            float(interest_context.bce_euribor_12m_percent)
        )
    negotiation_ref_rows = mss.fixed_rate_negotiation_reference_rows()

    return render_template(
        "spending_plan/mortgage.html",
        result=result,
        sim_form=sim_form,
        ltv_ratio_max=int(mss.LTV_RATIO_MAX_PERCENT),
        interest_context=interest_context,
        negotiation_hints=negotiation_hints,
        negotiation_ref_rows=negotiation_ref_rows,
        defaults={
            "notary": mss.DEFAULT_NOTARY,
            "registry": mss.DEFAULT_REGISTRY,
            "gestoria": mss.DEFAULT_GESTORIA,
            "tasacion": mss.DEFAULT_TASACION,
        },
    )


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
