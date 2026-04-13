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
            # Legacy (tailwind-like names) — mantener por compatibilidad.
            ('blue', 'Azul (clásico)'),
            ('indigo', 'Índigo (clásico)'),
            ('green', 'Verde (clásico)'),
            ('gray', 'Gris (clásico)'),
            # Paleta ampliada (HEX). Basada en nombres/hex de la UI.
            ('#DC2127', 'Tomate — #DC2127'),
            ('#FF887C', 'Flamingo — #FF887C'),
            ('#FFB878', 'Mandarina — #FFB878'),
            ('#FBD75B', 'Plátano — #FBD75B'),
            ('#7AE7BF', 'Salvia — #7AE7BF'),
            ('#51B749', 'Albahaca — #51B749'),
            ('#46D6DB', 'Pavo real — #46D6DB'),
            ('#5484ED', 'Arándano — #5484ED'),
            ('#A4BDFC', 'Lavanda — #A4BDFC'),
            ('#DBADFF', 'Uva — #DBADFF'),
            ('#616161', 'Grafito — #616161'),
        ],
        default='blue',
        render_kw={'class': 'form-input'}
    )
    submit = SubmitField('Guardar')
