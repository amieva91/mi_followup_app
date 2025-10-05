"""
Blueprint de autenticación
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User
from app.forms import LoginForm, RegisterForm, RequestResetForm, ResetPasswordForm
from app.utils.email import send_reset_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevo usuario"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Crear nuevo usuario
        user = User(
            username=form.username.data,
            email=form.email.data.lower()
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('¡Cuenta creada exitosamente! Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)


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

