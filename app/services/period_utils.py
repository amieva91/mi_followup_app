"""
Period Utilities - Sprint 4 Refinamientos
Funciones para calcular rangos de fechas según períodos seleccionados
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def get_period_dates(period='all'):
    """
    Calcula las fechas de inicio y fin para un período específico
    
    Args:
        period (str): Código del período
            - 'all': Todo el tiempo
            - 'ytd': Año actual (Year To Date)
            - 'year_YYYY': Año específico (ej: 'year_2024')
            - 'last_12m': Últimos 12 meses
            - 'last_6m': Últimos 6 meses
            - 'last_3m': Últimos 3 meses
            - 'last_1m': Último mes
            - 'custom': Personalizado (requiere start_date y end_date externos)
    
    Returns:
        tuple: (start_date, end_date) como objetos datetime
               start_date es None para 'all' (sin límite)
    """
    today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if period == 'all':
        return (None, today)
    
    elif period == 'ytd':
        # Año actual: desde 1 enero hasta hoy
        start = datetime(today.year, 1, 1, 0, 0, 0)
        return (start, today)
    
    elif period.startswith('year_'):
        # Año específico: 1 enero - 31 diciembre
        year = int(period.split('_')[1])
        start = datetime(year, 1, 1, 0, 0, 0)
        end = datetime(year, 12, 31, 23, 59, 59, 999999)
        return (start, end)
    
    elif period == 'last_12m':
        # Últimos 12 meses
        start = today - relativedelta(months=12)
        return (start, today)
    
    elif period == 'last_6m':
        # Últimos 6 meses
        start = today - relativedelta(months=6)
        return (start, today)
    
    elif period == 'last_3m':
        # Últimos 3 meses
        start = today - relativedelta(months=3)
        return (start, today)
    
    elif period == 'last_1m':
        # Último mes
        start = today - relativedelta(months=1)
        return (start, today)
    
    else:
        # Por defecto: todo el tiempo
        return (None, today)


def get_period_label(period='all'):
    """
    Obtiene la etiqueta legible de un período
    
    Args:
        period (str): Código del período
    
    Returns:
        str: Etiqueta para mostrar en UI
    """
    labels = {
        'all': 'Todo el tiempo',
        'ytd': f'Año actual ({datetime.now().year})',
        'last_12m': 'Últimos 12 meses',
        'last_6m': 'Últimos 6 meses',
        'last_3m': 'Últimos 3 meses',
        'last_1m': 'Último mes',
    }
    
    if period.startswith('year_'):
        year = period.split('_')[1]
        return f'Año {year}'
    
    return labels.get(period, 'Todo el tiempo')


def get_available_periods():
    """
    Obtiene la lista de períodos disponibles para el selector
    
    Returns:
        list: Lista de tuplas (código, etiqueta)
    """
    current_year = datetime.now().year
    
    periods = [
        ('all', 'Todo el tiempo'),
        ('ytd', f'Año actual ({current_year})'),
    ]
    
    # Añadir años anteriores (hasta 5 años atrás)
    for year in range(current_year - 1, current_year - 6, -1):
        if year >= 2017:  # No mostrar años muy antiguos
            periods.append((f'year_{year}', str(year)))
    
    # Añadir períodos relativos
    periods.extend([
        ('last_12m', 'Últimos 12 meses'),
        ('last_6m', 'Últimos 6 meses'),
        ('last_3m', 'Últimos 3 meses'),
        ('last_1m', 'Último mes'),
    ])
    
    return periods


def filter_transactions_by_period(transactions, period='all', start_date=None, end_date=None):
    """
    Filtra una lista de transacciones por período
    
    Args:
        transactions: QuerySet o lista de transacciones
        period (str): Código del período
        start_date (datetime): Fecha inicio personalizada (opcional)
        end_date (datetime): Fecha fin personalizada (opcional)
    
    Returns:
        list: Transacciones filtradas
    """
    # Si se proporcionan fechas personalizadas, usar esas
    if start_date or end_date:
        period_start = start_date
        period_end = end_date
    else:
        period_start, period_end = get_period_dates(period)
    
    # Filtrar transacciones
    filtered = []
    for txn in transactions:
        txn_date = txn.transaction_date
        
        # Si no hay fecha de inicio (período 'all'), solo verificar fin
        if period_start is None:
            if txn_date <= period_end:
                filtered.append(txn)
        else:
            # Verificar rango completo
            if period_start <= txn_date <= period_end:
                filtered.append(txn)
    
    return filtered

