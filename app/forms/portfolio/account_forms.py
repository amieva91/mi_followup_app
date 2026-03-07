"""Formularios para cuentas de broker"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from app.models import Broker

# Brokers principales a mostrar en el desplegable (evita DEGIRO_ACCOUNT, DEGIRO_TRANSACTIONS, etc.)
BROKER_WHITELIST = {'IBKR', 'DeGiro', 'Manual', 'Revolut', 'Commodities'}


class BrokerAccountForm(FlaskForm):
    """Formulario para crear/editar cuenta de broker"""
    broker_id = SelectField('Broker', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    broker_name_new = StringField(
        'Nombre del broker',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'Ej: Binance, Revolut, Kraken...'}
    )
    account_name = StringField('Nombre de la Cuenta', validators=[DataRequired(), Length(max=100)])
    base_currency = SelectField('Divisa Base', choices=[
        ('EUR', 'EUR - Euro'), ('USD', 'USD'), ('GBP', 'GBP'), ('CHF', 'CHF')], validators=[DataRequired()])
    submit = SubmitField('Guardar Cuenta')

    def __init__(self, add_new_broker_option=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_new_broker_option = add_new_broker_option
        brokers = Broker.query.filter_by(is_active=True).filter(Broker.name.in_(BROKER_WHITELIST)).order_by(Broker.name).all()
        choices = [(b.id, f"{b.name} - {b.full_name or b.name}") for b in brokers]
        if add_new_broker_option:
            choices = [('', '➕ Crear nuevo broker...')] + choices
        self.broker_id.choices = choices

    def validate_broker_id(self, field):
        """Debe elegir broker existente o indicar nombre de uno nuevo"""
        if self.add_new_broker_option:
            if not field.data and (self.broker_name_new.data or '').strip():
                return  # broker_name_new proporcionado, ok
            if not field.data and not (self.broker_name_new.data or '').strip():
                raise ValidationError('Selecciona un broker existente o escribe el nombre de uno nuevo.')
