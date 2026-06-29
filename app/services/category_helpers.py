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
            'category_id': None,
        }
    return {
        'icon': cat.icon or '📈',
        'name': STOCK_MARKET_CATEGORY_NAME,
        'category_id': cat.id,
    }


def category_filter_ids_for_list(category) -> list:
    """
    IDs para filtrar listados: la categoría seleccionada y, si es padre, sus hijas.
    """
    if category is None:
        return []
    ids = [int(category.id)]
    if category.parent_id is None:
        ids.extend(int(c.id) for c in category.children.all())
    return ids


def get_income_category_filter_ids(user_id: int, category_id: int) -> list:
    cat = IncomeCategory.query.filter_by(id=int(category_id), user_id=user_id).first()
    return category_filter_ids_for_list(cat) if cat else []


def get_expense_category_filter_ids(user_id: int, category_id: int) -> list:
    cat = ExpenseCategory.query.filter_by(id=int(category_id), user_id=user_id).first()
    return category_filter_ids_for_list(cat) if cat else []


def filter_synthetic_entries_for_category_ids(
    synthetic_entries: dict,
    category_ids: list,
    user_id: int,
    *,
    side: str,
) -> dict:
    """Limita filas sintéticas (Ajustes / Stock Market) al filtro de categoría activo."""
    if not synthetic_entries or not category_ids:
        return synthetic_entries or {}

    model = IncomeCategory if side == 'income' else ExpenseCategory
    stock_market = model.query.filter_by(
        user_id=user_id,
        name=STOCK_MARKET_CATEGORY_NAME,
    ).first()
    ajustes = model.query.filter_by(
        user_id=user_id,
        name=AJUSTES_CATEGORY_NAME,
    ).first()
    include_stock_market = stock_market is not None and int(stock_market.id) in category_ids
    include_ajustes = ajustes is not None and int(ajustes.id) in category_ids

    filtered = {}
    for key, data in synthetic_entries.items():
        stock_market_amount = float(data.get('stock_market', 0) or 0) if include_stock_market else 0.0
        ajuste_amount = float(data.get('ajuste', 0) or 0) if include_ajustes else 0.0
        if stock_market_amount <= 0 and ajuste_amount <= 0:
            continue
        row = dict(data)
        row['stock_market'] = round(stock_market_amount, 2)
        row['ajuste'] = round(ajuste_amount, 2)
        filtered[key] = row
    return filtered


def build_orphan_synthetic_entries(
    user_id: int,
    synthetic_entries: dict,
    movement_model,
    category_filter_ids: list | None = None,
) -> list:
    """
    Meses con filas sintéticas visibles pero sin movimientos reales en el ámbito del filtro.
    Con filtro de categoría, solo cuenta ingresos/gastos de esas categorías (padre + hijas).
    """
    if not synthetic_entries:
        return []

    months_query = movement_model.query.filter_by(user_id=user_id)
    if category_filter_ids:
        months_query = months_query.filter(
            movement_model.category_id.in_(category_filter_ids)
        )

    months_with_real = set()
    for row in months_query.with_entities(
        db.func.extract('year', movement_model.date).label('year'),
        db.func.extract('month', movement_model.date).label('month'),
    ).distinct().all():
        months_with_real.add((int(row.year), int(row.month)))

    orphans = []
    for (year, month), data in sorted(synthetic_entries.items(), reverse=True):
        if (year, month) in months_with_real:
            continue
        stock_market_amount = float(data.get('stock_market', 0) or 0)
        ajuste_amount = float(data.get('ajuste', 0) or 0)
        if stock_market_amount <= 0 and ajuste_amount <= 0:
            continue
        orphans.append({
            'year': year,
            'month': month,
            'month_label': data['month_label'],
            'ajuste': data.get('ajuste', 0),
            'stock_market': data.get('stock_market', 0),
            'include_adjustment_in_metrics': data.get(
                'include_adjustment_in_metrics', True
            ),
        })
    return orphans


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
