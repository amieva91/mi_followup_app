"""
Filtros personalizados para templates Jinja2
"""

MESES_ES = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
)


def format_month_es(value):
    """Formatea una fecha como 'Enero 2025' en español."""
    if value is None:
        return ''
    return f"{MESES_ES[value.month - 1]} {value.year}"


def format_number_eu(value):
    """
    Formatea un número en formato europeo sin decimales innecesarios
    Ejemplos:
        200.0 -> "200"
        200.5 -> "200,50"
        1234.56 -> "1.234,56"
    """
    if value is None:
        return "-"
    
    # Convertir a float
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    
    # Verificar si tiene decimales significativos
    if num == int(num):
        # Sin decimales
        formatted = f"{int(num):,}".replace(",", ".")
    else:
        # Con decimales (2 dígitos)
        formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    return formatted


def format_decimal_eu(value, decimals=2):
    """
    Formatea un número en formato europeo con decimales fijos
    Ejemplos:
        1234.56 -> "1.234,56"
        1234.5 -> "1.234,50"
    """
    if value is None:
        return "-"
    
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    
    formatted = f"{num:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def user_has_module(user, key):
    """Indica si el usuario tiene el módulo activado. Compatible con AnonymousUser y User antiguo."""
    if not user or not getattr(user, 'is_authenticated', False) or not user.is_authenticated:
        return False
    if not hasattr(user, 'has_module'):
        return True  # Usuario antiguo sin enabled_modules: mostrar todo
    return user.has_module(key)


def register_filters(app):
    """
    Registra los filtros personalizados en la aplicación Flask
    """
    app.jinja_env.filters['number_eu'] = format_number_eu
    app.jinja_env.filters['decimal_eu'] = format_decimal_eu
    app.jinja_env.filters['month_es'] = format_month_es
    app.jinja_env.filters['user_has_module'] = user_has_module

