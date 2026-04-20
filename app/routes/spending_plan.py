"""
Planificación de gastos / presupuestos (rama experimentos).
"""
import json
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_login import login_required, current_user

from app import db
from app.models.spending_plan import SpendingPlanGoal
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


def _merge_mortgage_target_into_extra(extra, td):
    """Una fecha en formulario: copia a extra_json como loan_payment_start (compra = 1.ª cuota)."""
    if not extra or td is None:
        return extra
    try:
        d = json.loads(extra)
        if not isinstance(d, dict):
            return extra
        d["loan_payment_start"] = td.isoformat()[:10]
        return json.dumps(d, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return extra


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
    data["open_edit_goal_id"] = request.args.get("edit_goal", type=int)
    resp = make_response(render_template("spending_plan/index.html", **data))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    resp.headers["Pragma"] = "no-cache"
    return resp


@spending_plan_bp.route("/objetivo", methods=["POST"])
@login_required
def add_goal():
    wants_json = "application/json" in (request.headers.get("Accept") or "") or request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest"
    if not request.form.get("csrf_token"):
        flash("Sesión expirada.", "error")
        if wants_json:
            return jsonify({"ok": False, "error_message": "Sesión expirada."}), 400
        return redirect(url_for("spending_plan.index"))
    try:
        gtype = (request.form.get("goal_type") or "generic").strip().lower()
        update_id = request.form.get("update_goal_id", type=int)
        if update_id and gtype == "mortgage":
            title = request.form.get("title") or ""
            amount = float(request.form.get("amount_total") or 0)
            priority = int(request.form.get("priority") or 3)
            td = _parse_target_date(request.form.get("target_date") or "")
            extra = (request.form.get("extra_json") or "").strip() or None
            extra = _merge_mortgage_target_into_extra(extra, td)
            sps.update_mortgage_goal(
                current_user.id,
                update_id,
                title,
                amount,
                priority,
                td,
                extra or "{}",
            )
            flash("Objetivo hipoteca actualizado.", "success")
            if wants_json:
                return jsonify({"ok": True})
            return redirect(url_for("spending_plan.index"))

        title = request.form.get("title") or ""
        amount = float(request.form.get("amount_total") or 0)
        priority = int(request.form.get("priority") or 3)
        td = _parse_target_date(request.form.get("target_date") or "")
        extra = (request.form.get("extra_json") or "").strip() or None
        if gtype == "mortgage" and extra:
            extra = _merge_mortgage_target_into_extra(extra, td)
        raw_inst = request.form.get("installment_months")
        date_fixed = bool(request.form.get("date_fixed"))
        try:
            pay_mode, installment_months = sps.pay_options_from_installment_field(
                raw_inst
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("spending_plan.index"))
        sps.add_goal(
            current_user.id,
            title,
            amount,
            priority,
            td,
            gtype,
            extra_json=extra,
            pay_mode=pay_mode,
            installment_months=installment_months,
            date_fixed=date_fixed,
        )
        flash("Objetivo añadido.", "success")
        if wants_json:
            return jsonify({"ok": True})
    except ValueError as e:
        msg = str(e)
        flash(msg, "error")
        if wants_json and (request.form.get("goal_type") or "generic").strip().lower() == "generic":
            sug = sps.suggest_adjustments_for_generic(
                current_user.id,
                None,
                request.form.get("title") or "",
                float(request.form.get("amount_total") or 0),
                int(request.form.get("priority") or 3),
                _parse_target_date(request.form.get("target_date") or ""),
                request.form.get("installment_months"),
                bool(request.form.get("date_fixed")),
            )
            return jsonify({"ok": False, "error_message": msg, "suggestions": sug}), 400
        if wants_json:
            return jsonify({"ok": False, "error_message": msg}), 400
    except Exception as e:
        db.session.rollback()
        msg = f"No se pudo añadir: {e}"
        flash(msg, "error")
        if wants_json:
            return jsonify({"ok": False, "error_message": msg}), 500
    return redirect(url_for("spending_plan.index"))


@spending_plan_bp.route("/objetivo/<int:goal_id>/editar", methods=["GET", "POST"])
@login_required
def edit_goal(goal_id: int):
    g = SpendingPlanGoal.query.filter_by(
        id=goal_id, user_id=current_user.id, goal_type="generic"
    ).first()
    if not g:
        flash("Objetivo no encontrado.", "error")
        return redirect(url_for("spending_plan.index"))
    if request.method == "GET":
        return redirect(url_for("spending_plan.index", edit_goal=goal_id))
    if request.method == "POST":
        wants_json = "application/json" in (request.headers.get("Accept") or "") or request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest"
        if not request.form.get("csrf_token"):
            flash("Sesión expirada.", "error")
            if wants_json:
                return jsonify({"ok": False, "error_message": "Sesión expirada."}), 400
            return redirect(url_for("spending_plan.index"))
        try:
            title = request.form.get("title") or ""
            amount = float(request.form.get("amount_total") or 0)
            priority = int(request.form.get("priority") or 3)
            td = _parse_target_date(request.form.get("target_date") or "")
            raw_inst = request.form.get("installment_months")
            date_fixed = bool(request.form.get("date_fixed"))
            try:
                pay_mode, installment_months = sps.pay_options_from_installment_field(
                    raw_inst
                )
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("spending_plan.index"))
            sps.update_generic_goal(
                current_user.id,
                goal_id,
                title,
                amount,
                priority,
                td,
                pay_mode=pay_mode,
                installment_months=installment_months,
                date_fixed=date_fixed,
            )
            flash("Objetivo actualizado y plan replanificado.", "success")
            if wants_json:
                return jsonify({"ok": True})
        except ValueError as e:
            msg = str(e)
            flash(msg, "error")
            if wants_json:
                sug = sps.suggest_adjustments_for_generic(
                    current_user.id,
                    goal_id,
                    request.form.get("title") or "",
                    float(request.form.get("amount_total") or 0),
                    int(request.form.get("priority") or 3),
                    _parse_target_date(request.form.get("target_date") or ""),
                    request.form.get("installment_months"),
                    bool(request.form.get("date_fixed")),
                )
                return jsonify({"ok": False, "error_message": msg, "suggestions": sug}), 400
        except Exception as e:
            db.session.rollback()
            msg = f"No se pudo guardar: {e}"
            flash(msg, "error")
            if wants_json:
                return jsonify({"ok": False, "error_message": msg}), 500
        return redirect(url_for("spending_plan.index"))


def _sim_form_from_mortgage_goal(goal: SpendingPlanGoal) -> dict:
    sim_form = _default_mortgage_form()
    if not goal or not goal.extra_json:
        return sim_form
    try:
        ex = json.loads(goal.extra_json)
    except (json.JSONDecodeError, TypeError):
        return sim_form
    if not isinstance(ex, dict):
        return sim_form
    if ex.get("purchase_price") is not None:
        sim_form["purchase_price"] = str(ex.get("purchase_price"))
    if ex.get("savings_cash") is not None:
        sim_form["savings"] = str(ex.get("savings_cash"))
    if ex.get("years") is not None:
        sim_form["years"] = str(int(ex.get("years")))
    if ex.get("annual_interest_percent") is not None:
        sim_form["annual_interest_percent"] = str(ex.get("annual_interest_percent"))
    try:
        itp = float(ex.get("itp_percent") or 6)
    except (TypeError, ValueError):
        itp = 6.0
    sim_form["first_home"] = itp <= 6.5
    return sim_form


def _negotiation_reference_rate_percent(sim_form: dict) -> float:
    """Tipo fijo del formulario como referencia para la heurística de negociación."""
    raw = (sim_form.get("annual_interest_percent") or "").strip().replace(",", ".")
    if not raw:
        return 3.5
    try:
        v = float(raw)
        return max(0.0, min(25.0, v))
    except ValueError:
        return 3.5


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
    edit_goal = None
    purchase_date_value = ""

    edit_param = request.args.get("edit", type=int)
    if request.method == "POST":
        edit_param = request.form.get("edit_goal_id", type=int) or edit_param

    if edit_param:
        mg = SpendingPlanGoal.query.filter_by(
            id=edit_param, user_id=current_user.id, goal_type="mortgage"
        ).first()
        if mg:
            edit_goal = mg
            sim_form = _sim_form_from_mortgage_goal(mg)
            if mg.target_date:
                purchase_date_value = mg.target_date.isoformat()
            else:
                try:
                    ex = json.loads(mg.extra_json or "{}")
                    if isinstance(ex, dict) and ex.get("loan_payment_start"):
                        purchase_date_value = str(ex.get("loan_payment_start"))[:10]
                except (json.JSONDecodeError, TypeError):
                    pass

    if interest_context and interest_context.bce_euribor_12m_percent is not None:
        if not edit_goal:
            sim_form["annual_interest_percent"] = (
                f"{float(interest_context.bce_euribor_12m_percent):.2f}"
            )

    if request.method == "POST" and request.form.get("action") == "simulate":
        if not request.form.get("csrf_token"):
            flash("Sesión expirada.", "error")
            eid_redir = request.form.get("edit_goal_id", type=int)
            return redirect(
                url_for(
                    "spending_plan.mortgage_simulator",
                    **({"edit": eid_redir} if eid_redir else {}),
                )
            )
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
        eid = request.form.get("edit_goal_id", type=int)
        if eid:
            mg = SpendingPlanGoal.query.filter_by(
                id=eid, user_id=current_user.id, goal_type="mortgage"
            ).first()
            if mg:
                edit_goal = mg
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

    negotiation_ref_e = _negotiation_reference_rate_percent(sim_form)
    negotiation_hints = mss.fixed_rate_negotiation_hints(negotiation_ref_e)
    negotiation_ref_rows = mss.fixed_rate_negotiation_band_rows(negotiation_ref_e)

    return render_template(
        "spending_plan/mortgage.html",
        result=result,
        sim_form=sim_form,
        ltv_ratio_max=int(mss.LTV_RATIO_MAX_PERCENT),
        interest_context=interest_context,
        negotiation_hints=negotiation_hints,
        negotiation_ref_e=negotiation_ref_e,
        negotiation_ref_rows=negotiation_ref_rows,
        edit_goal=edit_goal,
        purchase_date_value=purchase_date_value,
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
