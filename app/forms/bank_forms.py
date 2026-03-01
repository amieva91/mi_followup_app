"""
Formularios para bancos
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length


class BankForm(FlaskForm):
    """Formulario para crear/editar banco"""
    name = StringField(
        'Nombre del banco',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='Máximo 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: BBVA, ING, N26...', 'class': 'form-input'}
    )
    icon = StringField(
        'Icono (emoji)',
        validators=[Length(max=10)],
        default='🏦',
        render_kw={'placeholder': '🏦', 'class': 'form-input'}
    )
    color = SelectField(
        'Color',
        choices=[
            ('blue', 'Azul'),
            ('indigo', 'Índigo'),
            ('green', 'Verde'),
            ('gray', 'Gris'),
        ],
        default='blue',
        render_kw={'class': 'form-input'}
    )
    submit = SubmitField('Guardar')
