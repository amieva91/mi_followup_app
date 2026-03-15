"""
Servicio para operaciones de administración sobre usuarios (eliminar usuario y todos sus datos).
"""
from app import db
from app.models import (
    User,
    Expense,
    Income,
    ExpenseCategory,
    IncomeCategory,
    DebtPlan,
    RealEstateProperty,
    PropertyValuation,
    Bank,
    BankBalance,
    PortfolioHolding,
    Transaction,
    CashFlow,
    BrokerAccount,
    Watchlist,
    WatchlistConfig,
    ReportSettings,
    ReportTemplate,
    CompanyReport,
    AssetAboutSummary,
    MetricsCache,
    DashboardSummaryCache,
    PortfolioMetrics,
)
from app.models.api_call_log import ApiCallLog


def delete_user_and_data(user_id: int) -> tuple[bool, str]:
    """
    Elimina un usuario y todos sus datos en orden para respetar FKs.
    No elimina Assets ni AssetRegistry (son globales).
    Returns:
        (success, message)
    """
    user = User.query.get(user_id)
    if not user:
        return False, "Usuario no encontrado"
    if user.is_admin:
        return False, "No se puede eliminar un usuario administrador"

    try:
        # 1. Gastos (referencian category y debt_plan_id)
        Expense.query.filter_by(user_id=user_id).delete()
        # 2. Ingresos
        Income.query.filter_by(user_id=user_id).delete()
        # 3. Planes de deuda (referencian category, property_id)
        DebtPlan.query.filter_by(user_id=user_id).delete()
        # 4. Tasaciones de inmuebles (por propiedad)
        props = RealEstateProperty.query.filter_by(user_id=user_id).all()
        for p in props:
            PropertyValuation.query.filter_by(property_id=p.id).delete()
        # 5. Inmuebles
        RealEstateProperty.query.filter_by(user_id=user_id).delete()
        # 6. Saldos bancarios y bancos
        BankBalance.query.filter_by(user_id=user_id).delete()
        Bank.query.filter_by(user_id=user_id).delete()
        # 7. Holdings
        PortfolioHolding.query.filter_by(user_id=user_id).delete()
        # 8. CashFlow y Transaction (referencian account_id)
        accounts = BrokerAccount.query.filter_by(user_id=user_id).all()
        for acc in accounts:
            CashFlow.query.filter_by(account_id=acc.id).delete()
            Transaction.query.filter_by(account_id=acc.id).delete()
        # 9. Cuentas broker
        BrokerAccount.query.filter_by(user_id=user_id).delete()
        # 10. Watchlist y config
        Watchlist.query.filter_by(user_id=user_id).delete()
        WatchlistConfig.query.filter_by(user_id=user_id).delete()
        # 11. Informes y reportes
        ReportSettings.query.filter_by(user_id=user_id).delete()
        ReportTemplate.query.filter_by(user_id=user_id).delete()
        CompanyReport.query.filter_by(user_id=user_id).delete()
        AssetAboutSummary.query.filter_by(user_id=user_id).delete()
        # 12. Caches
        MetricsCache.query.filter_by(user_id=user_id).delete()
        DashboardSummaryCache.query.filter_by(user_id=user_id).delete()
        # 13. Métricas portfolio
        PortfolioMetrics.query.filter_by(user_id=user_id).delete()
        # 14. Logs de API (opcional, pueden quedar con user_id null si se prefiere)
        ApiCallLog.query.filter_by(user_id=user_id).delete()
        # 15. Categorías (después de gastos/ingresos)
        ExpenseCategory.query.filter_by(user_id=user_id).delete()
        IncomeCategory.query.filter_by(user_id=user_id).delete()
        # 16. Usuario
        db.session.delete(user)
        db.session.commit()
        return True, f"Usuario {user.username} y todos sus datos eliminados correctamente"
    except Exception as e:
        db.session.rollback()
        return False, str(e)
