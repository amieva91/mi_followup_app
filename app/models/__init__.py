"""
Modelos de la aplicación
"""
from app.models.user import User, MODULES, AVATARS
from app.models.expense import ExpenseCategory, Expense
from app.models.income import IncomeCategory, Income
from app.models.broker import Broker, BrokerAccount
from app.models.asset import Asset, PriceHistory
from app.models.asset_registry import AssetRegistry
from app.models.asset_delisting import AssetDelisting, DELISTING_TYPES
from app.models.mapping_registry import MappingRegistry
from app.models.portfolio import PortfolioHolding
from app.models.transaction import Transaction, CashFlow
from app.models.metrics import PortfolioMetrics
from app.models.metrics_cache import MetricsCache
from app.models.dashboard_summary_cache import DashboardSummaryCache
from app.models.portfolio_evolution_cache import PortfolioEvolutionCache
from app.models.portfolio_benchmarks_cache import PortfolioBenchmarksCache
from app.models.watchlist import Watchlist, WatchlistConfig
from app.models.company_report import ReportSettings, ReportTemplate, CompanyReport, AssetAboutSummary
from app.models.debt_plan import DebtPlan
from app.models.real_estate import RealEstateProperty, PropertyValuation, PROPERTY_TYPES, PROPERTY_ICONS, get_property_icon
from app.models.bank import Bank, BankBalance
from app.models.dashboard_config import UserDashboardConfig, DEFAULT_WIDGETS
from app.models.api_call_log import ApiCallLog
from app.models.user_login_log import UserLoginLog
from app.models.price_polling_state import PricePollingState
from app.models.cache_rebuild_state import CacheRebuildState
from app.models.benchmark_global_quote import BenchmarkGlobalQuote
from app.models.benchmark_global_daily import BenchmarkGlobalDaily, BenchmarkGlobalState

__all__ = [
    'User', 'MODULES', 'AVATARS', 
    'ExpenseCategory', 'Expense', 
    'IncomeCategory', 'Income',
    'Broker', 'BrokerAccount',
    'Asset', 'PriceHistory',
    'AssetRegistry',
    'AssetDelisting',
    'DELISTING_TYPES',
    'MappingRegistry',
    'PortfolioHolding',
    'Transaction', 'CashFlow',
    'PortfolioMetrics',
    'MetricsCache',
    'DashboardSummaryCache',
    'PortfolioEvolutionCache',
    'PortfolioBenchmarksCache',
    'Watchlist',
    'WatchlistConfig',
    'ReportSettings',
    'ReportTemplate',
    'CompanyReport',
    'AssetAboutSummary',
    'DebtPlan',
    'RealEstateProperty', 'PropertyValuation', 'PROPERTY_TYPES', 'PROPERTY_ICONS', 'get_property_icon',
    'Bank', 'BankBalance',
    'UserDashboardConfig', 'DEFAULT_WIDGETS',
    'ApiCallLog',
    'UserLoginLog',
    'PricePollingState',
    'CacheRebuildState',
    'BenchmarkGlobalQuote',
    'BenchmarkGlobalDaily',
    'BenchmarkGlobalState',
]

