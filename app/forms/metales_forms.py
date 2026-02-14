"""Formularios para el módulo Metales"""
from flask_wtf import FlaskForm
from wtforms import SelectField, FloatField, DateField, TextAreaField, SubmitField, RadioField
from wtforms.validators import DataRequired, NumberRange, Optional


class MetalTransactionForm(FlaskForm):
    """Compra o venta de metal"""
    metal_id = SelectField('Metal', coerce=int, validators=[DataRequired()])
    transaction_type = RadioField('Tipo', choices=[('BUY', 'Compra'), ('SELL', 'Venta')], default='BUY')
    unit = RadioField('Unidad', choices=[('g', 'Gramos (g)'), ('oz', 'Onzas troy (oz)')], default='g')
    quantity_grams = FloatField('Cantidad', validators=[
        DataRequired(),
        NumberRange(min=0.0001, message='La cantidad debe ser positiva')
    ])
    total_amount = FloatField('Precio total (EUR)', validators=[
        DataRequired(),
        NumberRange(min=0, message='El importe debe ser mayor o igual a 0')
    ])
    transaction_date = DateField('Fecha', validators=[DataRequired()])
    notes = TextAreaField('Notas', validators=[Optional()])
    submit = SubmitField('Registrar')
