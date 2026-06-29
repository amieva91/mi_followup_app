"""
Helpers para categorías del sistema (Ajustes, etc.)
"""
from app import db
from app.models import IncomeCategory, ExpenseCategory


AJUSTES_CATEGORY_NAME = 'Ajustes'
AJUSTES_ICON = '⚖️'

DIVIDENDOS_CATEGORY_NAME = 'Dividendos'
DEPOSITO_BROKER_PREFIX = 'Deposito en Broker '
STOCK_MARKET_CATEGORY_NAME = 'Stock Market'


def get_or_create_stock_market_income_category(user_id):
    """Obtiene o crea la categoría Stock Market para ingresos (retiradas broker)."""
    cat = IncomeCategory.query.filter_by(
        user_id=user_id,
        name=STOCK_MARKET_CATEGORY_NAME
    ).first()
    if not cat:
        cat = IncomeCategory(
            user_id=user_id,
            name=STOCK_MARKET_CATEGORY_NAME,
            icon='📈',
            color='green',
            parent_id=None
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def get_or_create_stock_market_expense_category(user_id):
    """Obtiene o crea la categoría Stock Market para gastos (depósitos broker)."""
    cat = ExpenseCategory.query.filter_by(
        user_id=user_id,
        name=STOCK_MARKET_CATEGORY_NAME
    ).first()
    if not cat:
        cat = ExpenseCategory(
            user_id=user_id,
            name=STOCK_MARKET_CATEGORY_NAME,
            icon='📈',
            color='gray',
            parent_id=None
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def get_or_create_ajustes_income_category(user_id):
    """Obtiene o crea la categoría Ajustes para ingresos. Retorna la categoría."""
    cat = IncomeCategory.query.filter_by(
        user_id=user_id,
        name=AJUSTES_CATEGORY_NAME
    ).first()
    if not cat:
        cat = IncomeCategory(
            user_id=user_id,
            name=AJUSTES_CATEGORY_NAME,
            icon=AJUSTES_ICON,
            color='gray',
            parent_id=None
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def get_or_create_ajustes_expense_category(user_id):
    """Obtiene o crea la categoría Ajustes para gastos. Retorna la categoría."""
    cat = ExpenseCategory.query.filter_by(
        user_id=user_id,
        name=AJUSTES_CATEGORY_NAME
    ).first()
    if not cat:
        cat = ExpenseCategory(
            user_id=user_id,
            name=AJUSTES_CATEGORY_NAME,
            icon=AJUSTES_ICON,
            color='gray',
            parent_id=None
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def is_ajustes_category(category):
    """Indica si la categoría es la reservada para ajustes del sistema."""
    return category and category.name == AJUSTES_CATEGORY_NAME


def is_stock_market_category(category):
    """Indica si la categoría es la reservada para movimientos broker (Stock Market)."""
    return category and category.name == STOCK_MARKET_CATEGORY_NAME


def ensure_stock_market_income_category_exists(user_id):
    """Crea la categoría Stock Market de ingresos si no existe (para configurar jerarquía)."""
    return get_or_create_stock_market_income_category(user_id)


def ensure_stock_market_expense_category_exists(user_id):
    """Crea la categoría Stock Market de gastos si no existe (para configurar jerarquía)."""
    return get_or_create_stock_market_expense_category(user_id)


def get_stock_market_display(user_id, side='income'):
    """
    Metadatos de presentación de Stock Market (icono, padre configurado).
    side: 'income' | 'expense'
    """
    if side == 'expense':
        cat = ExpenseCategory.query.filter_by(
            user_id=user_id,
            name=STOCK_MARKET_CATEGORY_NAME,
        ).first()
    else:
        cat = IncomeCategory.query.filter_by(
            user_id=user_id,
            name=STOCK_MARKET_CATEGORY_NAME,
        ).first()
    if not cat:
        return {
            'icon': '📈',
            'name': STOCK_MARKET_CATEGORY_NAME,
            'parent_name': None,
            'category_id': None,
        }
    parent_name = None
    if cat.parent_id:
        parent = cat.parent
        if parent:
            parent_name = parent.name
    return {
        'icon': cat.icon or '📈',
        'name': STOCK_MARKET_CATEGORY_NAME,
        'parent_name': parent_name,
        'category_id': cat.id,
    }


def get_or_create_dividendos_category(user_id):
    """Obtiene o crea la categoría Dividendos para ingresos (retiradas broker)."""
    cat = IncomeCategory.query.filter_by(
        user_id=user_id,
        name=DIVIDENDOS_CATEGORY_NAME
    ).first()
    if not cat:
        cat = IncomeCategory(
            user_id=user_id,
            name=DIVIDENDOS_CATEGORY_NAME,
            icon='📈',
            color='green',
            parent_id=None
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def get_or_create_deposito_broker_category(user_id, broker_name):
    """Obtiene o crea la categoría 'Deposito en Broker X' para gastos."""
    name = f"{DEPOSITO_BROKER_PREFIX}{broker_name}"
    cat = ExpenseCategory.query.filter_by(
        user_id=user_id,
        name=name
    ).first()
    if not cat:
        cat = ExpenseCategory(
            user_id=user_id,
            name=name,
            icon='🏦',
            color='gray',
            parent_id=None
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def filter_editable_categories(categories):
    """Excluye Ajustes de una lista de categorías (para formularios)."""
    return [c for c in categories if c.name != AJUSTES_CATEGORY_NAME]
