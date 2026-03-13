"""
Rutas para exportar e importar datos de usuario en Excel (.xlsx)
"""
from datetime import datetime
from flask import render_template, send_file, request, flash, redirect, url_for
from flask_login import login_required, current_user
from io import BytesIO

from app.routes import portfolio_bp
from app.services.data_export_import_service import export_user_data, import_user_data


@portfolio_bp.route('/data-export-import')
@login_required
def data_export_import():
    """Página Import/Export para backup y restauración de datos"""
    return render_template('portfolio/data_export_import.html')


@portfolio_bp.route('/data-export-import/download')
@login_required
def data_export_download():
    """Descarga el .xlsx con todos los datos del usuario"""
    buf = export_user_data(current_user.id)
    date_str = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"followup_backup_{current_user.username}_{date_str}.xlsx"
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@portfolio_bp.route('/data-export-import/import', methods=['POST'])
@login_required
def data_import_submit():
    """Procesa la subida de un archivo .xlsx para restaurar datos"""
    if 'file' not in request.files:
        flash('No se ha seleccionado ningún archivo.', 'error')
        return redirect(url_for('portfolio.data_export_import'))
    f = request.files['file']
    if f.filename == '':
        flash('No se ha seleccionado ningún archivo.', 'error')
        return redirect(url_for('portfolio.data_export_import'))
    if not f.filename.lower().endswith('.xlsx'):
        flash('El archivo debe ser un Excel (.xlsx).', 'error')
        return redirect(url_for('portfolio.data_export_import'))
    content = f.read()
    ok, msg, stats = import_user_data(current_user.id, content)
    if ok:
        flash(msg, 'success')
    else:
        flash(msg, 'error')
    return redirect(url_for('portfolio.data_export_import'))
