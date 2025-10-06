"""
Formularios para gastos e ingresos
"""
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TextAreaField, DateField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError
from datetime import date


class ExpenseCategoryForm(FlaskForm):
    """Formulario para categorías de gastos"""
    
    name = StringField(
        'Nombre de la categoría',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='Máximo 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Alimentación, Transporte, Ocio...', 'class': 'form-input'}
    )
    
    icon = StringField(
        'Icono (emoji)',
        validators=[Length(max=50)],
        default='💰',
        render_kw={'placeholder': '💰', 'class': 'form-input'}
    )
    
    color = SelectField(
        'Color',
        choices=[
            ('gray', 'Gris'),
            ('red', 'Rojo'),
            ('yellow', 'Amarillo'),
            ('green', 'Verde'),
            ('blue', 'Azul'),
            ('indigo', 'Índigo'),
            ('purple', 'Morado'),
            ('pink', 'Rosa')
        ],
        default='gray',
        render_kw={'class': 'form-input'}
    )
    
    parent_id = SelectField(
        'Categoría padre (opcional)',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-input'}
    )
    
    submit = SubmitField('Guardar Categoría')


class IncomeCategoryForm(FlaskForm):
    """Formulario para categorías de ingresos"""
    
    name = StringField(
        'Nombre de la categoría',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='Máximo 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Freelance, Bonos, Inversiones...', 'class': 'form-input'}
    )
    
    icon = StringField(
        'Icono (emoji)',
        validators=[Length(max=50)],
        default='💵',
        render_kw={'placeholder': '💵', 'class': 'form-input'}
    )
    
    color = SelectField(
        'Color',
        choices=[
            ('green', 'Verde'),
            ('blue', 'Azul'),
            ('indigo', 'Índigo'),
            ('purple', 'Morado'),
            ('yellow', 'Amarillo')
        ],
        default='green',
        render_kw={'class': 'form-input'}
    )
    
    submit = SubmitField('Guardar Categoría')


class ExpenseForm(FlaskForm):
    """Formulario para registrar gastos"""
    
    category_id = SelectField(
        'Categoría',
        coerce=int,
        validators=[DataRequired(message='Selecciona una categoría')],
        render_kw={'class': 'form-input'}
    )
    
    amount = FloatField(
        'Monto (€)',
        validators=[
            DataRequired(message='El monto es requerido'),
            NumberRange(min=0.01, message='El monto debe ser mayor a 0')
        ],
        render_kw={'placeholder': '0.00', 'step': '0.01', 'class': 'form-input'}
    )
    
    description = StringField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es requerida'),
            Length(max=255, message='Máximo 255 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Compra en supermercado', 'class': 'form-input'}
    )
    
    date = DateField(
        'Fecha',
        validators=[DataRequired(message='La fecha es requerida')],
        default=date.today,
        render_kw={'class': 'form-input'}
    )
    
    notes = TextAreaField(
        'Notas (opcional)',
        validators=[Optional()],
        render_kw={'placeholder': 'Información adicional...', 'rows': '3', 'class': 'form-input'}
    )
    
    is_recurring = BooleanField(
        'Gasto recurrente',
        default=False
    )
    
    recurrence_frequency = SelectField(
        'Frecuencia',
        choices=[
            ('', '-- Selecciona --'),
            ('daily', 'Diaria'),
            ('weekly', 'Semanal'),
            ('monthly', 'Mensual'),
            ('yearly', 'Anual')
        ],
        validators=[Optional()],
        render_kw={'class': 'form-input'}
    )
    
    recurrence_end_date = DateField(
        'Fecha fin de recurrencia (opcional)',
        validators=[Optional()],
        render_kw={'class': 'form-input'}
    )
    
    submit = SubmitField('Guardar Gasto')
    
    def validate_recurrence_frequency(self, field):
        """Validar que si es recurrente, tenga frecuencia"""
        if self.is_recurring.data and not field.data:
            raise ValidationError('Debes seleccionar una frecuencia para gastos recurrentes')


class IncomeForm(FlaskForm):
    """Formulario para registrar ingresos"""
    
    category_id = SelectField(
        'Categoría',
        coerce=int,
        validators=[DataRequired(message='Selecciona una categoría')],
        render_kw={'class': 'form-input'}
    )
    
    amount = FloatField(
        'Monto (€)',
        validators=[
            DataRequired(message='El monto es requerido'),
            NumberRange(min=0.01, message='El monto debe ser mayor a 0')
        ],
        render_kw={'placeholder': '0.00', 'step': '0.01', 'class': 'form-input'}
    )
    
    description = StringField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es requerida'),
            Length(max=255, message='Máximo 255 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Pago por proyecto freelance', 'class': 'form-input'}
    )
    
    date = DateField(
        'Fecha',
        validators=[DataRequired(message='La fecha es requerida')],
        default=date.today,
        render_kw={'class': 'form-input'}
    )
    
    notes = TextAreaField(
        'Notas (opcional)',
        validators=[Optional()],
        render_kw={'placeholder': 'Información adicional...', 'rows': '3', 'class': 'form-input'}
    )
    
    is_recurring = BooleanField(
        'Ingreso recurrente',
        default=False
    )
    
    recurrence_frequency = SelectField(
        'Frecuencia',
        choices=[
            ('', '-- Selecciona --'),
            ('weekly', 'Semanal'),
            ('monthly', 'Mensual'),
            ('yearly', 'Anual')
        ],
        validators=[Optional()],
        render_kw={'class': 'form-input'}
    )
    
    recurrence_end_date = DateField(
        'Fecha fin de recurrencia (opcional)',
        validators=[Optional()],
        render_kw={'class': 'form-input'}
    )
    
    submit = SubmitField('Guardar Ingreso')
    
    def validate_recurrence_frequency(self, field):
        """Validar que si es recurrente, tenga frecuencia"""
        if self.is_recurring.data and not field.data:
            raise ValidationError('Debes seleccionar una frecuencia para ingresos recurrentes')

