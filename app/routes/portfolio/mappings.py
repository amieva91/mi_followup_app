"""
Rutas de gestión de mapeos (MIC→Yahoo, Exchange→Yahoo, etc.)
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from app.routes import portfolio_bp
from app import db


@portfolio_bp.route('/mappings')
@login_required
def mappings():
    """Página de gestión de mapeos"""
    from app.models import MappingRegistry

    search = request.args.get('search', '').strip()
    mapping_type_filter = request.args.get('mapping_type', '').strip()
    country_filter = request.args.get('country', '').strip()

    query = MappingRegistry.query

    if search:
        query = query.filter(
            db.or_(
                MappingRegistry.source_key.ilike(f'%{search}%'),
                MappingRegistry.target_value.ilike(f'%{search}%'),
                MappingRegistry.description.ilike(f'%{search}%')
            )
        )
    if mapping_type_filter:
        query = query.filter_by(mapping_type=mapping_type_filter)
    if country_filter:
        query = query.filter_by(country=country_filter)

    query = query.order_by(MappingRegistry.mapping_type, MappingRegistry.source_key)
    mappings_list = query.all()

    stats = {
        'total': MappingRegistry.query.count(),
        'mic_to_yahoo': MappingRegistry.query.filter_by(mapping_type='MIC_TO_YAHOO').count(),
        'exchange_to_yahoo': MappingRegistry.query.filter_by(mapping_type='EXCHANGE_TO_YAHOO').count(),
        'degiro_to_ibkr': MappingRegistry.query.filter_by(mapping_type='DEGIRO_TO_IBKR').count(),
        'active': MappingRegistry.query.filter_by(is_active=True).count(),
        'inactive': MappingRegistry.query.filter_by(is_active=False).count(),
    }

    countries = db.session.query(MappingRegistry.country).distinct().filter(
        MappingRegistry.country.isnot(None)
    ).order_by(MappingRegistry.country).all()
    countries = [c[0] for c in countries]

    return render_template('portfolio/mappings.html',
                          mappings=mappings_list,
                          stats=stats,
                          countries=countries)


@portfolio_bp.route('/mappings/new', methods=['POST'])
@login_required
def mappings_new():
    """Crear nuevo mapeo"""
    from app.models import MappingRegistry

    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))

    mapping_type = request.form.get('mapping_type', '').strip()
    source_key = request.form.get('source_key', '').strip().upper()
    target_value = request.form.get('target_value', '').strip()
    description = request.form.get('description', '').strip()
    country = request.form.get('country', '').strip().upper() or None

    if not mapping_type or not source_key or not target_value:
        flash('❌ Faltan campos obligatorios (Tipo, Clave, Valor)', 'error')
        return redirect(url_for('portfolio.mappings'))

    existing = MappingRegistry.query.filter_by(
        mapping_type=mapping_type,
        source_key=source_key
    ).first()
    if existing:
        flash(f'❌ Ya existe un mapeo {mapping_type}: {source_key}', 'error')
        return redirect(url_for('portfolio.mappings'))

    mapping = MappingRegistry(
        mapping_type=mapping_type,
        source_key=source_key,
        target_value=target_value,
        description=description,
        country=country,
        created_by='MANUAL'
    )
    db.session.add(mapping)
    db.session.commit()
    flash(f'✅ Mapeo creado: {source_key} → {target_value}', 'success')
    return redirect(url_for('portfolio.mappings'))


@portfolio_bp.route('/mappings/<int:id>/edit', methods=['POST'])
@login_required
def mappings_edit(id):
    """Editar mapeo existente"""
    from app.models import MappingRegistry

    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))

    mapping = MappingRegistry.query.get_or_404(id)
    mapping.target_value = request.form.get('target_value', '').strip()
    mapping.description = request.form.get('description', '').strip()
    mapping.country = request.form.get('country', '').strip().upper() or None
    db.session.commit()
    flash(f'✅ Mapeo actualizado: {mapping.source_key} → {mapping.target_value}', 'success')
    return redirect(url_for('portfolio.mappings'))


@portfolio_bp.route('/mappings/<int:id>/delete', methods=['POST'])
@login_required
def mappings_delete(id):
    """Eliminar mapeo"""
    from app.models import MappingRegistry

    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))

    mapping = MappingRegistry.query.get_or_404(id)
    source_key = mapping.source_key
    db.session.delete(mapping)
    db.session.commit()
    flash(f'🗑️ Mapeo eliminado: {source_key}', 'info')
    return redirect(url_for('portfolio.mappings'))


@portfolio_bp.route('/mappings/<int:id>/toggle', methods=['POST'])
@login_required
def mappings_toggle(id):
    """Activar/desactivar mapeo"""
    from app.models import MappingRegistry

    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        flash('❌ Token CSRF inválido', 'error')
        return redirect(url_for('portfolio.mappings'))

    mapping = MappingRegistry.query.get_or_404(id)
    mapping.is_active = not mapping.is_active
    db.session.commit()
    status = 'activado' if mapping.is_active else 'desactivado'
    flash(f'✅ Mapeo {status}: {mapping.source_key}', 'success')
    return redirect(url_for('portfolio.mappings'))
