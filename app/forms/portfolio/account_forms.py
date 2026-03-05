"""Formularios para cuentas de broker"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length
from app.models import Broker


class BrokerAccountForm(FlaskForm):
    """Formulario para crear/editar cuenta de broker"""
    broker_id = SelectField('Broker', coerce=int, validators=[DataRequired()])
    account_name = StringField('Nombre de la Cuenta', validators=[DataRequired(), Length(max=100)])
    account_number = StringField('Número de Cuenta (opcional)', validators=[Optional(), Length(max=50)])
    base_currency = SelectField('Divisa Base', choices=[
        ('EUR', 'EUR - Euro'), ('USD', 'USD'), ('GBP', 'GBP'), ('CHF', 'CHF')], validators=[DataRequired()])
    submit = SubmitField('Guardar Cuenta')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.broker_id.choices = [(b.id, f"{b.name} - {b.full_name}") for b in Broker.query.filter_by(is_active=True).all()]
