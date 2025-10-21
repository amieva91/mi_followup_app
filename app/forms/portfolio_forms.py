"""
Formularios para gestión de portfolio
"""
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, BooleanField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from flask_login import current_user
from app.models import Broker, BrokerAccount, Asset


class BrokerAccountForm(FlaskForm):
    """Formulario para crear/editar cuenta de broker"""
    broker_id = SelectField('Broker', coerce=int, validators=[DataRequired()])
    account_name = StringField('Nombre de la Cuenta', validators=[DataRequired(), Length(max=100)])
    account_number = StringField('Número de Cuenta (opcional)', validators=[Optional(), Length(max=50)])
    base_currency = SelectField('Divisa Base', choices=[
        ('EUR', 'EUR - Euro'),
        ('USD', 'USD - Dólar'),
        ('GBP', 'GBP - Libra'),
        ('CHF', 'CHF - Franco Suizo'),
    ], validators=[DataRequired()])
    submit = SubmitField('Guardar Cuenta')
    
    def __init__(self, *args, **kwargs):
        super(BrokerAccountForm, self).__init__(*args, **kwargs)
        # Cargar brokers disponibles
        self.broker_id.choices = [
            (b.id, f"{b.name} - {b.full_name}") 
            for b in Broker.query.filter_by(is_active=True).all()
        ]


class ManualTransactionForm(FlaskForm):
    """Formulario para entrada manual de transacciones (compra/venta)"""
    account_id = SelectField('Cuenta', coerce=int, validators=[DataRequired()])
    
    # Datos del activo
    symbol = StringField('Símbolo', validators=[DataRequired(), Length(max=20)])
    isin = StringField('ISIN (opcional)', validators=[Optional(), Length(max=12)])
    asset_name = StringField('Nombre del Activo', validators=[DataRequired(), Length(max=200)])
    asset_type = SelectField('Tipo de Activo', choices=[
        ('Stock', 'Acción'),
        ('ETF', 'ETF'),
        ('Bond', 'Bono'),
        ('Crypto', 'Criptomoneda'),
    ], validators=[DataRequired()])
    currency = SelectField('Divisa', choices=[
        ('USD', 'USD'), ('EUR', 'EUR'), ('GBP', 'GBP'),
        ('HKD', 'HKD'), ('CAD', 'CAD'), ('PLN', 'PLN'),
        ('NOK', 'NOK'), ('SGD', 'SGD'),
    ], validators=[DataRequired()])
    
    # Identificadores de mercado (editables para correcciones)
    exchange = StringField('Exchange (código unificado)', validators=[Optional(), Length(max=10)])
    mic = StringField('MIC ISO 10383', validators=[Optional(), Length(min=4, max=4)])
    yahoo_suffix = StringField('Sufijo Yahoo (ej: .MC, .L)', validators=[Optional(), Length(max=5)])
    
    # Datos de la transacción
    transaction_type = SelectField('Tipo de Operación', choices=[
        ('BUY', 'Compra'),
        ('SELL', 'Venta'),
    ], validators=[DataRequired()])
    
    transaction_date = DateField('Fecha de Transacción', validators=[DataRequired()])
    quantity = FloatField('Cantidad', validators=[
        DataRequired(),
        NumberRange(min=0.000001, message='La cantidad debe ser positiva')
    ])
    price = FloatField('Precio por Unidad', validators=[
        DataRequired(),
        NumberRange(min=0.000001, message='El precio debe ser positivo')
    ])
    
    # Costes
    commission = FloatField('Comisión', validators=[Optional(), NumberRange(min=0)], default=0.0)
    fees = FloatField('Otros Gastos', validators=[Optional(), NumberRange(min=0)], default=0.0)
    tax = FloatField('Impuestos/Retención', validators=[Optional(), NumberRange(min=0)], default=0.0)
    
    notes = TextAreaField('Notas (opcional)', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Registrar Transacción')
    
    def __init__(self, *args, **kwargs):
        super(ManualTransactionForm, self).__init__(*args, **kwargs)
        # Cargar cuentas del usuario
        self.account_id.choices = [
            (acc.id, f"{acc.account_name} ({acc.broker.name})") 
            for acc in BrokerAccount.query.filter_by(
                user_id=current_user.id, 
                is_active=True
            ).all()
        ]



