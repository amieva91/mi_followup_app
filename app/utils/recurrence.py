"""
Utilidades para manejar gastos/ingresos recurrentes
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid


def generate_recurrence_dates(start_date, frequency, end_date=None):
    """
    Genera una lista de fechas basándose en la frecuencia de recurrencia.
    
    Args:
        start_date (date): Fecha de inicio
        frequency (str): 'daily', 'weekly', 'monthly', 'yearly'
        end_date (date, optional): Fecha de fin. Si es None, genera hasta hoy.
    
    Returns:
        list: Lista de objetos date
    """
    dates = [start_date]
    current_date = start_date
    
    # Si no hay fecha de fin, generar hasta hoy
    if end_date is None:
        end_date = datetime.now().date()
    
    # No generar si la fecha de inicio es futura
    if start_date > datetime.now().date():
        return [start_date]
    
    # Asegurar que end_date no sea mayor que hoy
    today = datetime.now().date()
    if end_date > today:
        end_date = today
    
    # Generar fechas según frecuencia
    while True:
        if frequency == 'daily':
            current_date = current_date + timedelta(days=1)
        elif frequency == 'weekly':
            current_date = current_date + timedelta(weeks=1)
        elif frequency == 'monthly':
            current_date = current_date + relativedelta(months=1)
        elif frequency == 'yearly':
            current_date = current_date + relativedelta(years=1)
        else:
            break
        
        if current_date > end_date:
            break
        
        dates.append(current_date)
    
    return dates


def create_recurrence_instances(model_class, base_instance, user_id):
    """
    Crea instancias recurrentes de un gasto/ingreso.
    
    Args:
        model_class: Clase del modelo (Expense o Income)
        base_instance: Instancia base con datos del formulario (no guardada aún)
        user_id: ID del usuario
    
    Returns:
        list: Lista de instancias creadas (sin commit)
    """
    instances = []
    
    # Si no es recurrente, solo devolver la instancia base
    if not base_instance.is_recurring:
        instances.append(base_instance)
        return instances
    
    # Generar un UUID único para agrupar esta serie recurrente
    group_id = str(uuid.uuid4())
    
    # Generar fechas de recurrencia
    dates = generate_recurrence_dates(
        base_instance.date,
        base_instance.recurrence_frequency,
        base_instance.recurrence_end_date
    )
    
    # Crear una instancia para cada fecha
    for date in dates:
        instance = model_class(
            user_id=user_id,
            category_id=base_instance.category_id,
            amount=base_instance.amount,
            description=base_instance.description,
            date=date,
            notes=base_instance.notes,
            is_recurring=True,  # Mantener el flag para identificarlas
            recurrence_frequency=base_instance.recurrence_frequency,
            recurrence_end_date=base_instance.recurrence_end_date,
            recurrence_group_id=group_id  # Asignar el mismo grupo a todas
        )
        instances.append(instance)
    
    return instances

