"""
Formularios de perfil / cuenta de usuario
"""
from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from flask_login import current_user
from app.models import User


def _validate_birth_year(form, field):
    """Valida año de nacimiento: vacío o entre 1900 y año actual."""
    if not field.data or not str(field.data).strip():
        return  # Optional: vacío es válido
    try:
        year = int(str(field.data).strip())
    except (ValueError, TypeError):
        raise ValidationError('Introduce un año válido (ej: 1991)')
    min_year, max_year = 1900, date.today().year
    if year < min_year or year > max_year:
        raise ValidationError(f'El año debe estar entre {min_year} y {max_year}')


class ProfileForm(FlaskForm):
    """Editar perfil: avatar, username, email, birth_year, módulos"""

    username = StringField(
        'Nombre de usuario',
        validators=[
            DataRequired(message='El nombre de usuario es requerido'),
            Length(min=3, max=50, message='Debe tener entre 3 y 50 caracteres'),
        ],
        render_kw={'placeholder': 'usuario123', 'class': 'form-input'},
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Email inválido'),
        ],
        render_kw={'placeholder': 'tu@email.com', 'class': 'form-input'},
    )
    birth_year = StringField(
        'Año de nacimiento',
        validators=[Optional(), _validate_birth_year],
        render_kw={'placeholder': '1990', 'class': 'form-input', 'inputmode': 'numeric', 'pattern': '[0-9]*'},
    )
    # Módulos: se generan dinámicamente en la ruta
    submit = SubmitField('Guardar cambios')

    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user and user.id != current_user.id:
            raise ValidationError('Ese nombre de usuario ya está en uso.')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data.lower()).first()
        if user and user.id != current_user.id:
            raise ValidationError('Ese email ya está registrado.')


class ChangePasswordForm(FlaskForm):
    """Cambiar contraseña"""

    current_password = PasswordField(
        'Contraseña actual',
        validators=[DataRequired(message='Requerida para confirmar')],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'},
    )
    password = PasswordField(
        'Nueva contraseña',
        validators=[
            DataRequired(message='La contraseña es requerida'),
            Length(min=6, message='Al menos 6 caracteres'),
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'},
    )
    confirm_password = PasswordField(
        'Confirmar nueva contraseña',
        validators=[
            DataRequired(message='Confirma tu contraseña'),
            EqualTo('password', message='Las contraseñas deben coincidir'),
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'},
    )
    submit = SubmitField('Cambiar contraseña')

    def validate_current_password(self, field):
        if not current_user.check_password(field.data):
            raise ValidationError('La contraseña actual no es correcta.')


class DeleteAccountForm(FlaskForm):
    """Formulario para borrar la cuenta (requiere confirmación con contraseña)"""

    password = PasswordField(
        'Contraseña',
        validators=[DataRequired(message='Introduce tu contraseña para confirmar')],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'},
    )
    confirm_text = StringField(
        'Escribe BORRAR para confirmar',
        validators=[
            DataRequired(message='Debes escribir BORRAR para confirmar'),
        ],
        render_kw={'placeholder': 'BORRAR', 'class': 'form-input'},
    )
    submit = SubmitField('Eliminar mi cuenta definitivamente')

    def validate_password(self, field):
        if not current_user.check_password(field.data):
            raise ValidationError('La contraseña no es correcta.')

    def validate_confirm_text(self, field):
        if field.data and field.data.strip().upper() != 'BORRAR':
            raise ValidationError('Debes escribir exactamente BORRAR para confirmar.')
