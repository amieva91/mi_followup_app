"""
Onboarding guiado del Dashboard por hitos de primer registro.

Este servicio centraliza toda la lógica para:
- Determinar hitos aplicables según módulos activos.
- Detectar hitos completados (primer registro por dominio).
- Calcular progreso y siguientes acciones.
- Controlar popups de onboarding (1 vez por hito completado) con persistencia.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app import db
from app.models import (
    Asset,
    Bank,
    DashboardOnboardingState,
    DebtPlan,
    Expense,
    Income,
    PortfolioHolding,
    RealEstateProperty,
    User,
)


@dataclass(frozen=True)
class MilestoneDef:
    key: str
    label: str
    module_key: str
    endpoint: str
    endpoint_kwargs: dict[str, Any] | None = None


class DashboardOnboardingService:
    MILESTONES: tuple[MilestoneDef, ...] = (
        MilestoneDef("banks", "Conectar tu primer banco", "finance", "banks.new"),
        MilestoneDef("incomes", "Registrar tu primer ingreso", "finance", "incomes.new"),
        MilestoneDef("expenses", "Registrar tu primer gasto", "finance", "expenses.new"),
        MilestoneDef("debts", "Registrar tu primera deuda", "finance", "debts.new", {"next": "debts"}),
        MilestoneDef("portfolio", "Importar o registrar acciones", "stock", "portfolio.import_csv"),
        MilestoneDef("crypto", "Registrar tu primera transacción crypto", "crypto", "crypto.transaction_new"),
        MilestoneDef("metales", "Registrar tu primera compra de metales", "metales", "metales.transaction_new"),
        MilestoneDef("real_estate", "Registrar tu primer inmueble", "real_estate", "real_estate.new"),
    )

    @staticmethod
    def _enabled_modules(user: User) -> set[str]:
        mods = user.get_enabled_modules() if hasattr(user, "get_enabled_modules") else []
        if isinstance(mods, list):
            return {str(m) for m in mods}
        return set()

    @staticmethod
    def _exists_any(model, user_id: int) -> bool:
        return db.session.query(model.id).filter(model.user_id == user_id).first() is not None

    @staticmethod
    def _portfolio_exists(user_id: int, asset_types: tuple[str, ...]) -> bool:
        q = (
            db.session.query(PortfolioHolding.id)
            .join(Asset, Asset.id == PortfolioHolding.asset_id)
            .filter(
                PortfolioHolding.user_id == user_id,
                PortfolioHolding.quantity > 0,
                Asset.asset_type.in_(asset_types),
            )
        )
        return q.first() is not None

    @staticmethod
    def _completed_milestones(user_id: int) -> set[str]:
        completed: set[str] = set()
        if DashboardOnboardingService._exists_any(Bank, user_id):
            completed.add("banks")
        if DashboardOnboardingService._exists_any(Income, user_id):
            completed.add("incomes")
        if DashboardOnboardingService._exists_any(Expense, user_id):
            completed.add("expenses")
        if DashboardOnboardingService._exists_any(DebtPlan, user_id):
            completed.add("debts")
        if DashboardOnboardingService._portfolio_exists(user_id, ("Stock", "ETF")):
            completed.add("portfolio")
        if DashboardOnboardingService._portfolio_exists(user_id, ("Crypto",)):
            completed.add("crypto")
        if DashboardOnboardingService._portfolio_exists(user_id, ("Commodity",)):
            completed.add("metales")
        if DashboardOnboardingService._exists_any(RealEstateProperty, user_id):
            completed.add("real_estate")
        return completed

    @staticmethod
    def _milestone_defs_by_module(enabled_modules: set[str]) -> list[MilestoneDef]:
        return [m for m in DashboardOnboardingService.MILESTONES if m.module_key in enabled_modules]

    @staticmethod
    def build_state(user: User) -> dict[str, Any]:
        enabled_modules = DashboardOnboardingService._enabled_modules(user)
        milestone_defs = DashboardOnboardingService._milestone_defs_by_module(enabled_modules)

        applicable_keys = [m.key for m in milestone_defs]
        completed_set = DashboardOnboardingService._completed_milestones(user.id)
        completed_keys = [k for k in applicable_keys if k in completed_set]
        pending_keys = [k for k in applicable_keys if k not in completed_set]

        state_row = DashboardOnboardingState.query.filter_by(user_id=user.id).first()
        notified = set((state_row.notified_milestones or []) if state_row else [])
        newly_completed = [k for k in completed_keys if k not in notified]

        total = len(applicable_keys)
        completed_count = len(completed_keys)
        percent = int(round((completed_count / total) * 100)) if total > 0 else 100

        def to_payload(keys: list[str]) -> list[dict[str, Any]]:
            payload = []
            by_key = {m.key: m for m in milestone_defs}
            for k in keys:
                m = by_key.get(k)
                if not m:
                    continue
                payload.append(
                    {
                        "key": m.key,
                        "label": m.label,
                        "module_key": m.module_key,
                        "endpoint": m.endpoint,
                        "endpoint_kwargs": m.endpoint_kwargs or {},
                    }
                )
            return payload

        return {
            "applicable_milestones": to_payload(applicable_keys),
            "completed_milestones": to_payload(completed_keys),
            "pending_milestones": to_payload(pending_keys),
            "newly_completed_milestones": to_payload(newly_completed),
            "completed_count": completed_count,
            "total_count": total,
            "progress_percent": percent,
            "show_initial_onboarding": total > 0 and completed_count == 0,
            "show_next_step_popup": completed_count > 0 and len(newly_completed) > 0,
        }

    @staticmethod
    def acknowledge_milestones(user_id: int, milestone_keys: list[str]) -> list[str]:
        valid_keys = {m.key for m in DashboardOnboardingService.MILESTONES}
        clean = [str(k) for k in (milestone_keys or []) if str(k) in valid_keys]
        if not clean:
            return []

        row = DashboardOnboardingState.query.filter_by(user_id=user_id).first()
        if not row:
            row = DashboardOnboardingState(
                user_id=user_id,
                notified_milestones=[],
            )
            db.session.add(row)

        current = set(row.notified_milestones or [])
        current.update(clean)
        row.notified_milestones = sorted(current)
        row.last_notified_at = datetime.utcnow()
        db.session.commit()
        return clean

