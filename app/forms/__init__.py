"""
Formularios de la aplicación
"""
from app.forms.auth_forms import LoginForm, RegisterForm, RequestResetForm, ResetPasswordForm
from app.forms.finance_forms import (
    ExpenseCategoryForm, IncomeCategoryForm,
    ExpenseForm, IncomeForm,
    DebtPlanForm, DebtPlanEditForm, DebtRestructureForm, DebtLimitForm
)
from app.forms.portfolio import BrokerAccountForm, ManualTransactionForm
from app.forms.bank_forms import BankForm

__all__ = [
    'LoginForm', 'RegisterForm', 'RequestResetForm', 'ResetPasswordForm',
    'ExpenseCategoryForm', 'IncomeCategoryForm', 'ExpenseForm', 'IncomeForm',
    'DebtPlanForm', 'DebtPlanEditForm', 'DebtRestructureForm', 'DebtLimitForm',
    'BrokerAccountForm', 'ManualTransactionForm',
    'BankForm'
]

