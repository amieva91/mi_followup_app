"""
Blueprint de autenticación
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import (
    User, MODULES, AVATARS,
    CashFlow, Transaction, PortfolioHolding, PortfolioMetrics, BrokerAccount,
    Expense, ExpenseCategory, Income, IncomeCategory, DebtPlan,
    Bank, BankBalance, Watchlist, WatchlistConfig,
    UserDashboardConfig, MetricsCache,
    ReportSettings, ReportTemplate, CompanyReport, AssetAboutSummary,
)
from app.forms import LoginForm, RegisterForm, RequestResetForm, ResetPasswordForm
from app.forms.profile_forms import ProfileForm, ChangePasswordForm, DeleteAccountForm
from app.utils.email import send_reset_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevo usuario"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        enabled = [k for k in MODULES.keys() if request.form.get('module_' + k) == 'on']
        if not enabled:
            enabled = list(MODULES.keys())  # Por defecto todos
        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
            enabled_modules=enabled
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('¡Cuenta creada exitosamente! Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form, modules=MODULES)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
                return redirect(url_for('auth.login'))
            
            login_user(user, remember=form.remember_me.data)
            user.update_last_login()
            
            # Redirigir a la página que intentaba acceder o al dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            flash(f'¡Bienvenido de vuelta, {user.username}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Email o contraseña incorrectos. Por favor intenta de nuevo.', 'error')
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def request_reset():
    """Solicitar reset de contraseña"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RequestResetForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_reset_email(user)
            flash('Se ha enviado un email con instrucciones para recuperar tu contraseña.', 'info')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/request_reset.html', form=form)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Perfil y configuración de cuenta"""
    user = db.session.get(User, current_user.id)
    form = ProfileForm(obj=user)
    # Solo rellenar el form con datos de BD en GET. En POST no tocar: ya tiene lo enviado por el usuario.
    if request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
        form.birth_year.data = str(user.birth_year) if user.birth_year is not None else ''

    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data.lower()
        by = form.birth_year.data
        try:
            current_user.birth_year = int(str(by).strip()) if by and str(by).strip() else None
        except (ValueError, TypeError):
            current_user.birth_year = None
        # Avatar: request.form mantiene "avatar_id" (0 = iniciales, 1+ = imagen)
        avatar_id = request.form.get('avatar_id', type=int)
        if avatar_id is not None:
            current_user.avatar_id = avatar_id if avatar_id in AVATARS else None
        # Módulos habilitados
        enabled = [k for k in MODULES.keys() if request.form.get('module_' + k) == 'on']
        current_user.enabled_modules = enabled if enabled else list(MODULES.keys())
        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('auth.profile'), code=303)

    response = make_response(render_template(
        'auth/profile.html',
        form=form,
        password_form=ChangePasswordForm(),
        delete_account_form=DeleteAccountForm(),
        modules=MODULES,
        avatars=AVATARS,
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@auth_bp.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    """Cambiar contraseña"""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.set_password(form.password.data)
        db.session.commit()
        flash('Contraseña cambiada correctamente.', 'success')
        return redirect(url_for('auth.profile'))
    # Si hay errores, volver a profile mostrando el formulario de contraseña
    user = db.session.get(User, current_user.id)
    profile_form = ProfileForm(obj=user)
    profile_form.username.data = user.username
    profile_form.email.data = user.email
    profile_form.birth_year.data = str(user.birth_year) if user.birth_year is not None else ''
    return render_template(
        'auth/profile.html',
        form=profile_form,
        password_form=form,
        delete_account_form=DeleteAccountForm(),
        modules=MODULES,
        avatars=AVATARS,
    )


def _delete_user_data(user_id):
    """Elimina todos los datos asociados al usuario (orden correcto por FKs)."""
    CashFlow.query.filter_by(user_id=user_id).delete()
    Transaction.query.filter_by(user_id=user_id).delete()
    for acc in BrokerAccount.query.filter_by(user_id=user_id).all():
        PortfolioHolding.query.filter_by(account_id=acc.id).delete()
        PortfolioMetrics.query.filter_by(account_id=acc.id).delete()
    PortfolioMetrics.query.filter_by(user_id=user_id).delete()
    BrokerAccount.query.filter_by(user_id=user_id).delete()
    Expense.query.filter_by(user_id=user_id).delete()
    ExpenseCategory.query.filter_by(user_id=user_id).delete()
    Income.query.filter_by(user_id=user_id).delete()
    IncomeCategory.query.filter_by(user_id=user_id).delete()
    DebtPlan.query.filter_by(user_id=user_id).delete()
    BankBalance.query.filter_by(user_id=user_id).delete()
    Bank.query.filter_by(user_id=user_id).delete()
    Watchlist.query.filter_by(user_id=user_id).delete()
    WatchlistConfig.query.filter_by(user_id=user_id).delete()
    UserDashboardConfig.query.filter_by(user_id=user_id).delete()
    MetricsCache.query.filter_by(user_id=user_id).delete()
    ReportTemplate.query.filter_by(user_id=user_id).delete()
    CompanyReport.query.filter_by(user_id=user_id).delete()
    AssetAboutSummary.query.filter_by(user_id=user_id).delete()
    ReportSettings.query.filter_by(user_id=user_id).delete()


@auth_bp.route('/profile/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Eliminar cuenta del usuario definitivamente"""
    form = DeleteAccountForm()
    if form.validate_on_submit():
        user_id = current_user.id
        _delete_user_data(user_id)
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
        logout_user()
        flash('Tu cuenta ha sido eliminada. Sentimos que te vayas.', 'info')
        return redirect(url_for('main.index'))
    # Si hay errores de validación, mostrar perfil con mensaje
    flash('No se pudo eliminar. Verifica la contraseña y que escribiste BORRAR.', 'error')
    user = db.session.get(User, current_user.id)
    profile_form = ProfileForm(obj=user)
    profile_form.username.data = user.username
    profile_form.email.data = user.email
    profile_form.birth_year.data = str(user.birth_year) if user.birth_year else ''
    return render_template(
        'auth/profile.html',
        form=profile_form,
        password_form=ChangePasswordForm(),
        delete_account_form=form,
        modules=MODULES,
        avatars=AVATARS,
    )


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Resetear contraseña con token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    user = User.verify_reset_token(token)
    
    if not user:
        flash('El link de recuperación es inválido o ha expirado.', 'error')
        return redirect(url_for('auth.request_reset'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Tu contraseña ha sido actualizada. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

