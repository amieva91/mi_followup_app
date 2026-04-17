"""
Planificación de gastos / presupuestos de objetivos (WIP, rama experimentos).
"""
from flask import Blueprint, render_template
from flask_login import login_required

spending_plan_bp = Blueprint("spending_plan", __name__, url_prefix="/planificacion")


@spending_plan_bp.route("/")
@login_required
def index():
    """Página principal del planificador (placeholder hasta motor y modelos)."""
    return render_template("spending_plan/index.html")
