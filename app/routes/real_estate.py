"""
Blueprint para el módulo Inmuebles (Real Estate)
"""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import RealEstateProperty, PropertyValuation, DebtPlan
from app.forms.real_estate_forms import RealEstatePropertyForm, PropertyValuationForm
from app.services.debt_service import DebtService

real_estate_bp = Blueprint('real_estate', __name__, url_prefix='/real-estate')


@real_estate_bp.route('/')
@login_required
def dashboard():
    """Listado de inmuebles con valor estimado e indicador de hipoteca"""
    DebtService.ensure_all_plans_have_installments(current_user.id)
    props = RealEstateProperty.query.filter_by(user_id=current_user.id).order_by(
        RealEstateProperty.address
    ).all()

    total_value = sum(p.get_estimated_value() for p in props)
    total_debt = 0
    for p in props:
        plan = DebtPlan.query.filter_by(property_id=p.id, status='ACTIVE').first()
        if plan:
            total_debt += DebtService.get_remaining_amount(plan.id, current_user.id)

    return render_template(
        'real_estate/dashboard.html',
        properties=props,
        total_value=total_value,
        total_debt=total_debt,
        DebtService=DebtService,
        DebtPlan=DebtPlan,
    )


@real_estate_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo inmueble"""
    form = RealEstatePropertyForm()
    if form.validate_on_submit():
        prop = RealEstateProperty(
            user_id=current_user.id,
            property_type=form.property_type.data,
            address=form.address.data.strip(),
            purchase_price=form.purchase_price.data,
            purchase_date=form.purchase_date.data,
            notes=form.notes.data.strip() if form.notes.data else None,
        )
        db.session.add(prop)
        db.session.commit()
        flash(f'Inmueble registrado: {prop.get_icon()} {prop.address}', 'success')
        return redirect(url_for('real_estate.dashboard'))

    return render_template('real_estate/form.html', form=form, title='Nuevo inmueble')


@real_estate_bp.route('/<int:id>')
@login_required
def detail(id):
    """Detalle del inmueble con tasaciones"""
    prop = RealEstateProperty.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    valuations = PropertyValuation.query.filter_by(property_id=prop.id).order_by(PropertyValuation.year.desc()).all()
    debt_plan = DebtPlan.query.filter_by(property_id=id, status='ACTIVE').first()
    remaining = DebtService.get_remaining_amount(debt_plan.id, current_user.id) if debt_plan else 0

    return render_template(
        'real_estate/detail.html',
        property=prop,
        valuations=valuations,
        debt_plan=debt_plan,
        remaining=remaining,
        DebtService=DebtService,
        current_year=date.today().year,
    )


@real_estate_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Editar inmueble"""
    prop = RealEstateProperty.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = RealEstatePropertyForm()
    if form.validate_on_submit():
        prop.property_type = form.property_type.data
        prop.address = form.address.data.strip()
        prop.purchase_price = form.purchase_price.data
        prop.purchase_date = form.purchase_date.data
        prop.notes = form.notes.data.strip() if form.notes.data else None
        db.session.commit()
        flash('Inmueble actualizado.', 'success')
        return redirect(url_for('real_estate.detail', id=id))

    if request.method == 'GET':
        form.property_type.data = prop.property_type
        form.address.data = prop.address
        form.purchase_price.data = prop.purchase_price
        form.purchase_date.data = prop.purchase_date
        form.notes.data = prop.notes or ''

    return render_template('real_estate/form.html', form=form, prop=prop, title='Editar inmueble')


@real_estate_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Eliminar inmueble. Si tiene hipoteca vinculada, elimina también el plan de deuda."""
    prop = RealEstateProperty.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    debt_plan = DebtPlan.query.filter_by(property_id=id).first()

    if debt_plan:
        DebtService.cancel_plan(debt_plan.id, current_user.id, delete_future_only=False)
        flash('Inmueble e hipoteca vinculada eliminados.', 'info')
    else:
        flash('Inmueble eliminado.', 'info')

    db.session.delete(prop)
    db.session.commit()
    return redirect(url_for('real_estate.dashboard'))


@real_estate_bp.route('/<int:id>/valuation/add', methods=['POST'])
@login_required
def add_valuation(id):
    """Añadir tasación anual"""
    prop = RealEstateProperty.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = PropertyValuationForm()
    if form.validate_on_submit():
        purchase_year = prop.purchase_date.year
        current_year = date.today().year
        year_val = form.year.data
        if year_val < purchase_year:
            flash(f'El año de tasación no puede ser anterior a la compra ({purchase_year})', 'error')
            return redirect(url_for('real_estate.detail', id=id))
        if year_val > current_year:
            flash(f'El año de tasación no puede ser posterior al actual ({current_year})', 'error')
            return redirect(url_for('real_estate.detail', id=id))
        existing = PropertyValuation.query.filter_by(property_id=id, year=form.year.data).first()
        if existing:
            existing.value = form.value.data
            flash(f'Tasación {form.year.data} actualizada.', 'success')
        else:
            val = PropertyValuation(
                property_id=id,
                year=form.year.data,
                value=form.value.data,
            )
            db.session.add(val)
            flash(f'Tasación {form.year.data} añadida.', 'success')
        db.session.commit()
    else:
        for _, errors in form.errors.items():
            for e in errors:
                flash(e, 'error')
                break
            break
    return redirect(url_for('real_estate.detail', id=id))


@real_estate_bp.route('/<int:prop_id>/valuation/<int:val_id>/delete', methods=['POST'])
@login_required
def delete_valuation(prop_id, val_id):
    """Eliminar tasación"""
    prop = RealEstateProperty.query.filter_by(id=prop_id, user_id=current_user.id).first_or_404()
    val = PropertyValuation.query.filter_by(id=val_id, property_id=prop_id).first_or_404()
    db.session.delete(val)
    db.session.commit()
    flash('Tasación eliminada.', 'info')
    return redirect(url_for('real_estate.detail', id=prop_id))
