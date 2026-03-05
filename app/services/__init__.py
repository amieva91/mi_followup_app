"""
API pública de servicios - FollowUp

Importar desde aquí para mantener consistencia y facilitar refactorings.

Ejemplo:
    from app.services import convert_to_eur, DebtService, BankService
"""
from app.services.currency_service import convert_to_eur, get_exchange_rates, get_cache_info
from app.services.debt_service import DebtService
from app.services.bank_service import BankService
from app.services.net_worth_service import get_dashboard_summary

__all__ = [
    # Currency
    'convert_to_eur',
    'get_exchange_rates',
    'get_cache_info',
    # Domain services
    'DebtService',
    'BankService',
    'get_dashboard_summary',
]
