"""
Formularios para el módulo Inmuebles
"""
from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField, FloatField, DateField, SelectField,
    TextAreaField, SubmitField, IntegerField, BooleanField
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length

from app.models.real_estate import PROPERTY_TYPES


class RealEstatePropertyForm(FlaskForm):
    """Formulario para crear/editar inmueble"""
    property_type = SelectField(
        'Tipo',
        choices=[('', '-- Selecciona --')] + list(PROPERTY_TYPES),
        validators=[DataRequired(message='Selecciona el tipo')],
        render_kw={'class': 'form-input'}
    )
    address = StringField(
        'Dirección',
        validators=[
            DataRequired(message='La dirección es requerida'),
            Length(max=255)
        ],
        render_kw={'placeholder': 'Calle, número, ciudad...', 'class': 'form-input'}
    )
    purchase_price = FloatField(
        'Precio de compra (€)',
        validators=[
            DataRequired(message='El precio es requerido'),
            NumberRange(min=0.01, message='Debe ser mayor a 0')
        ],
        render_kw={'placeholder': '0.00', 'step': '0.01', 'class': 'form-input'}
    )
    purchase_date = DateField(
        'Fecha de compra',
        validators=[DataRequired(message='La fecha es requerida')],
        default=date.today,
        render_kw={'class': 'form-input'}
    )
    notes = TextAreaField(
        'Notas (opcional)',
        validators=[Optional()],
        render_kw={'placeholder': 'Detalles adicionales...', 'rows': '2', 'class': 'form-input'}
    )
    submit = SubmitField('Guardar')


class PropertyValuationForm(FlaskForm):
    """Formulario para añadir tasación anual"""
    year = IntegerField(
        'Año',
        validators=[
            DataRequired(),
            NumberRange(min=1900, max=2100)
        ],
        default=date.today().year,
        render_kw={'class': 'form-input', 'min': '1900', 'max': '2100'}
    )
    value = FloatField(
        'Valor (€)',
        validators=[
            DataRequired(),
            NumberRange(min=0.01)
        ],
        render_kw={'placeholder': '0.00', 'step': '0.01', 'class': 'form-input'}
    )
    submit = SubmitField('Añadir tasación')
