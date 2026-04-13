"""
Formularios para bancos
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length


class BankForm(FlaskForm):
    """Formulario para crear/editar banco"""
    ICON_CHOICES = [
        ('🏦', 'Banco'),
        ('🦁', 'León (ej. ING)'),
        ('💳', 'Tarjeta'),
        ('💰', 'Ahorro'),
        ('🪙', 'Monedas'),
        ('📈', 'Inversión'),
        ('🌍', 'Internacional'),
        ('🏠', 'Hipoteca'),
    ]

    # Paleta (12) solicitada por el usuario:
    # - value: clave estable (se guarda en DB)
    # - label: Tonalidad (texto para el usuario)
    COLOR_CHOICES = [
        ('tomate', 'Rojo intenso'),
        ('flamingo', 'Rosa/Coral'),
        ('mandarina', 'Naranja claro'),
        ('calabaza', 'Naranja fuerte'),
        ('platano', 'Amarillo'),
        ('salvia', 'Verde menta'),
        ('albahaca', 'Verde oscuro'),
        ('pavo_real', 'Turquesa'),
        ('arandano', 'Azul medio'),
        ('lavanda', 'Morado claro'),
        ('uva', 'Violeta'),
        ('grafito', 'Gris oscuro'),
    ]

    name = StringField(
        'Nombre del banco',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='Máximo 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: BBVA, ING, N26...', 'class': 'form-input'}
    )
    icon = SelectField(
        'Icono (emoji)',
        choices=ICON_CHOICES,
        default='🏦',
        render_kw={'placeholder': '🏦', 'class': 'form-input'}
    )
    color = SelectField(
        'Color',
        choices=COLOR_CHOICES,
        default='arandano',
        render_kw={'class': 'form-input'}
    )
    submit = SubmitField('Guardar')
