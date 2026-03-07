"""
Formularios para gastos e ingresos
"""
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, TextAreaField, DateField, BooleanField, SelectField, SubmitField
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
    
    parent_id = SelectField(
        'Categoría padre (opcional)',
        coerce=int,
        validators=[Optional()],
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


class DebtPlanForm(FlaskForm):
    """Formulario para crear un plan de deuda (pago a plazos)"""

    name = StringField(
        'Nombre / Descripción',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=255, message='Máximo 255 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Ordenador portátil, TV Samsung...', 'class': 'form-input'}
    )

    total_amount = FloatField(
        'Importe total (€)',
        validators=[
            DataRequired(message='El importe es requerido'),
            NumberRange(min=0.01, message='El importe debe ser mayor a 0')
        ],
        render_kw={'placeholder': '0.00', 'step': '0.01', 'class': 'form-input'}
    )

    months = IntegerField(
        'Número de meses',
        validators=[
            DataRequired(message='Los meses son requeridos'),
            NumberRange(min=1, max=360, message='Entre 1 y 360 meses')
        ],
        render_kw={'placeholder': '12', 'min': '1', 'class': 'form-input'}
    )

    start_date = DateField(
        'Fecha de la primera cuota',
        validators=[DataRequired(message='La fecha es requerida')],
        default=date.today,
        render_kw={'class': 'form-input'}
    )

    category_id = SelectField(
        'Categoría del gasto',
        coerce=int,
        validators=[DataRequired(message='Selecciona una categoría')],
        render_kw={'class': 'form-input'}
    )

    notes = TextAreaField(
        'Notas (opcional)',
        validators=[Optional()],
        render_kw={'placeholder': 'Información adicional...', 'rows': '2', 'class': 'form-input'}
    )

    is_mortgage = BooleanField(
        '¿Es hipoteca de un inmueble registrado?',
        default=False
    )
    property_id = SelectField(
        'Inmueble',
        coerce=lambda x: int(x) if x and x != '' else None,
        validators=[Optional()],
        render_kw={'class': 'form-input'}
    )

    submit = SubmitField('Crear plan de deuda')


class DebtPlanEditForm(FlaskForm):
    """Formulario para editar un plan de deuda (mismos campos que crear)"""

    name = StringField(
        'Nombre / Descripción',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=255, message='Máximo 255 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Ordenador portátil, TV Samsung...', 'class': 'form-input'}
    )

    total_amount = FloatField(
        'Importe total (€)',
        validators=[
            DataRequired(message='El importe es requerido'),
            NumberRange(min=0.01, message='El importe debe ser mayor a 0')
        ],
        render_kw={'placeholder': '0.00', 'step': '0.01', 'class': 'form-input'}
    )

    months = IntegerField(
        'Número de meses',
        validators=[
            DataRequired(message='Los meses son requeridos'),
            NumberRange(min=1, max=360, message='Entre 1 y 360 meses')
        ],
        render_kw={'placeholder': '12', 'min': '1', 'class': 'form-input'}
    )

    start_date = DateField(
        'Fecha de la primera cuota',
        validators=[DataRequired(message='La fecha es requerida')],
        render_kw={'class': 'form-input'}
    )

    category_id = SelectField(
        'Categoría del gasto',
        coerce=int,
        validators=[DataRequired(message='Selecciona una categoría')],
        render_kw={'class': 'form-input'}
    )

    notes = TextAreaField(
        'Notas (opcional)',
        validators=[Optional()],
        render_kw={'placeholder': 'Información adicional...', 'rows': '2', 'class': 'form-input'}
    )

    submit = SubmitField('Guardar cambios')


class DebtRestructureForm(FlaskForm):
    """Formulario para reestructurar un plan (por cuota o por meses)"""

    restructure_mode = SelectField(
        'Reestructurar por',
        choices=[
            ('by_amount', 'Nueva cuota mensual (€)'),
            ('by_months', 'Número de meses restantes')
        ],
        validators=[DataRequired()],
        default='by_amount'
    )

    new_monthly_payment = FloatField(
        'Nueva cuota mensual (€)',
        validators=[Optional(), NumberRange(min=0.01, message='Debe ser mayor que 0')],
        render_kw={'placeholder': 'Ej: 150.00', 'step': '0.01', 'min': '0.01', 'class': 'form-input'}
    )

    new_months = IntegerField(
        'Meses restantes',
        validators=[Optional(), NumberRange(min=1, max=360, message='Entre 1 y 360')],
        render_kw={'placeholder': 'Ej: 12', 'min': '1', 'class': 'form-input'}
    )

    submit = SubmitField('Reestructurar plan')

    def validate_new_monthly_payment(self, field):
        if self.restructure_mode.data == 'by_amount' and (not field.data or field.data <= 0):
            raise ValidationError('Indica la nueva cuota mensual')

    def validate_new_months(self, field):
        if self.restructure_mode.data == 'by_months' and (not field.data or field.data < 1):
            raise ValidationError('Indica el número de meses')


class DebtLimitForm(FlaskForm):
    """Formulario para actualizar el límite de endeudamiento"""

    debt_limit_percent = FloatField(
        'Límite máximo de endeudamiento (% sobre ingresos)',
        validators=[
            DataRequired(message='El porcentaje es requerido'),
            NumberRange(min=5, max=100, message='Entre 5% y 100%')
        ],
        default=35.0,
        render_kw={'placeholder': '35', 'step': '0.5', 'min': '5', 'max': '100', 'class': 'form-input'}
    )

    submit = SubmitField('Guardar límite')

