"""
Rutas para el módulo Cryptomonedas
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from app.services.crypto_metrics import compute_crypto_metrics

crypto_bp = Blueprint('crypto', __name__, url_prefix='/crypto')


@crypto_bp.route('/')
@login_required
def dashboard():
    """Dashboard de cryptomonedas: fiat, cuasi-fiat, posiciones, rentabilidad"""
    metrics = compute_crypto_metrics(current_user.id)
    return render_template('crypto/dashboard.html', metrics=metrics)


@crypto_bp.route('/import')
@login_required
def import_csv():
    """Redirige a la subida de CSV de portfolio (soporta Revolut X)"""
    return redirect(url_for('portfolio.import_csv'))
