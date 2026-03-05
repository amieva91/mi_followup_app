"""Formularios para el módulo Criptomonedas"""
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, TextAreaField, SubmitField, RadioField
from wtforms.validators import DataRequired, Optional, NumberRange, Length


class CryptoTransactionForm(FlaskForm):
    """Compra o venta de criptomoneda"""
    account_id = SelectField(
        'Cuenta / Broker',
        coerce=lambda x: int(x) if x else None,
        validators=[DataRequired(message='Debes seleccionar una cuenta')]
    )
    symbol = StringField(
        'Símbolo',
        validators=[DataRequired(message='El símbolo es requerido'), Length(max=20)],
        render_kw={'placeholder': 'BTC, ETH, ADA, SOL...'}
    )
    transaction_type = RadioField(
        'Tipo',
        choices=[('BUY', 'Compra'), ('SELL', 'Venta')],
        default='BUY'
    )
    quantity = FloatField(
        'Cantidad',
        validators=[
            DataRequired(message='La cantidad es requerida'),
            NumberRange(min=0.00000001, message='La cantidad debe ser positiva')
        ],
        render_kw={'placeholder': 'Ej: 0.5'}
    )
    price = FloatField(
        'Precio por unidad (EUR)',
        validators=[
            DataRequired(message='El precio es requerido'),
            NumberRange(min=0, message='El precio debe ser mayor o igual a 0')
        ],
        render_kw={'placeholder': 'Ej: 45000'}
    )
    currency = SelectField(
        'Divisa',
        choices=[('EUR', 'EUR'), ('USD', 'USD')],
        default='EUR'
    )
    transaction_date = DateField('Fecha', validators=[DataRequired()])
    commission = FloatField('Comisión (EUR)', validators=[Optional()], default=0)
    notes = TextAreaField('Notas', validators=[Optional()])
    submit = SubmitField('Registrar')
