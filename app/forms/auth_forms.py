"""
Formularios de autenticación
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión"""
    
    email = StringField(
        'Email', 
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Email inválido')
        ],
        render_kw={'placeholder': 'tu@email.com', 'class': 'form-input'}
    )
    
    password = PasswordField(
        'Contraseña', 
        validators=[
            DataRequired(message='La contraseña es requerida')
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'}
    )
    
    remember_me = BooleanField('Recordarme')
    
    submit = SubmitField('Iniciar Sesión')


class RegisterForm(FlaskForm):
    """Formulario de registro"""
    
    username = StringField(
        'Nombre de usuario',
        validators=[
            DataRequired(message='El nombre de usuario es requerido'),
            Length(min=3, max=50, message='Debe tener entre 3 y 50 caracteres')
        ],
        render_kw={'placeholder': 'usuario123', 'class': 'form-input'}
    )
    
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Email inválido')
        ],
        render_kw={'placeholder': 'tu@email.com', 'class': 'form-input'}
    )
    
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es requerida'),
            Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'}
    )
    
    confirm_password = PasswordField(
        'Confirmar contraseña',
        validators=[
            DataRequired(message='Confirma tu contraseña'),
            EqualTo('password', message='Las contraseñas deben coincidir')
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'}
    )
    
    submit = SubmitField('Registrarse')
    
    def validate_username(self, username):
        """Validar que el username no exista"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ese nombre de usuario ya está en uso. Por favor elige otro.')
    
    def validate_email(self, email):
        """Validar que el email no exista"""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Ese email ya está registrado. Por favor usa otro o inicia sesión.')


class RequestResetForm(FlaskForm):
    """Formulario para solicitar reset de contraseña"""
    
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Email inválido')
        ],
        render_kw={'placeholder': 'tu@email.com', 'class': 'form-input'}
    )
    
    submit = SubmitField('Enviar link de recuperación')
    
    def validate_email(self, email):
        """Validar que el email exista"""
        user = User.query.filter_by(email=email.data.lower()).first()
        if not user:
            raise ValidationError('No existe una cuenta con ese email.')


class ResetPasswordForm(FlaskForm):
    """Formulario para resetear contraseña"""
    
    password = PasswordField(
        'Nueva contraseña',
        validators=[
            DataRequired(message='La contraseña es requerida'),
            Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'}
    )
    
    confirm_password = PasswordField(
        'Confirmar nueva contraseña',
        validators=[
            DataRequired(message='Confirma tu contraseña'),
            EqualTo('password', message='Las contraseñas deben coincidir')
        ],
        render_kw={'placeholder': '••••••••', 'class': 'form-input'}
    )
    
    submit = SubmitField('Cambiar contraseña')

