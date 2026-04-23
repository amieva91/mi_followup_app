"""
Motor de recomendaciones del Dashboard.

- Agrega recomendaciones por módulos (solo si hay registros).
- Integra alertas de salud financiera en el feed de recomendaciones.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import db
from app.models import (
    User,
    Income,
    Expense,
    Bank,
    BankBalance,
    DebtPlan,
    Transaction,
    PortfolioHolding,
    RealEstateProperty,
)


@dataclass(frozen=True)
class Recommendation:
    priority: str  # high|medium|low
    icon: str
    title: str
    text: str
    action: str | None = None
    source: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d = {
            "priority": self.priority,
            "icon": self.icon,
            "title": self.title,
            "text": self.text,
        }
        if self.action:
            d["action"] = self.action
        if self.source:
            d["source"] = self.source
        return d


class RecommendationService:
    @staticmethod
    def _has_any_finance_records(user_id: int) -> bool:
        # Fast-ish existence checks (SQLite): LIMIT 1.
        if Income.query.filter_by(user_id=user_id).first() is not None:
            return True
        if Expense.query.filter_by(user_id=user_id).first() is not None:
            return True
        if DebtPlan.query.filter_by(user_id=user_id).first() is not None:
            return True
        if (
            BankBalance.query.filter(
                BankBalance.user_id == user_id,
                BankBalance.amount != 0
            ).first()
            is not None
        ):
            return True
        return False

    @staticmethod
    def _enabled_modules(user: User) -> set[str]:
        mods = user.enabled_modules or []
        if isinstance(mods, list):
            return {str(m) for m in mods}
        return set()

    @staticmethod
    def build_for_dashboard(user_id: int, *, health_score: dict | None = None) -> list[dict[str, Any]]:
        """
        Recomendaciones unificadas para el dashboard.

        Reglas:
        - Solo incluir recomendaciones de áreas con registros.
        - Deduplicar por (title, text).
        - Orden por prioridad high->medium->low.
        """
        user = User.query.get(user_id)
        if not user:
            return []

        enabled = RecommendationService._enabled_modules(user)
        recs: list[Recommendation] = []

        # ---- Salud financiera: tips + alertas, solo si hay registros de finanzas ----
        active_months = int((health_score or {}).get("summary", {}).get("active_months") or 0)
        if health_score and RecommendationService._has_any_finance_records(user_id) and active_months >= 2:
            tips = health_score.get("tips") or []
            for t in tips:
                if not isinstance(t, dict):
                    continue
                recs.append(
                    Recommendation(
                        priority=str(t.get("priority") or "low"),
                        icon=str(t.get("icon") or "💡"),
                        title=str(t.get("title") or "Recomendación"),
                        text=str(t.get("text") or ""),
                        action=str(t.get("action") or ""),
                        source="health",
                    )
                )

            alerts = health_score.get("alerts") or []
            for a in alerts:
                if not isinstance(a, dict):
                    continue
                at = str(a.get("type") or "warning").lower()
                pr = "high" if at == "danger" else "medium"
                recs.append(
                    Recommendation(
                        priority=pr,
                        icon=str(a.get("icon") or "⚠️"),
                        title="Alerta",
                        text=str(a.get("text") or ""),
                        action="Revisa tu situación financiera",
                        source="health_alert",
                    )
                )

        # ---- Ideas de ampliación por módulos (mínimo viable, solo con registros) ----
        # Finance: si hay ingresos pero no bancos, sugerir añadir bancos para cash (ejemplo simple).
        if "finance" in enabled:
            has_income = Income.query.filter_by(user_id=user_id).first() is not None
            has_bank = Bank.query.filter_by(user_id=user_id).first() is not None
            if has_income and not has_bank:
                recs.append(
                    Recommendation(
                        priority="low",
                        icon="🏦",
                        title="Añade tus bancos",
                        text="Ya tienes ingresos registrados. Añadir bancos te permitirá ver el cash y su evolución en el dashboard.",
                        action="Ir a Bancos y añadir uno",
                        source="finance",
                    )
                )

        # Stock: si el módulo está habilitado y hay transacciones pero no holdings activos, sugerir revisar import.
        if "stock" in enabled:
            has_tx = Transaction.query.filter_by(user_id=user_id).first() is not None
            has_holdings = (
                PortfolioHolding.query.filter_by(user_id=user_id)
                .filter(PortfolioHolding.quantity > 0)
                .first()
                is not None
            )
            if has_tx and not has_holdings:
                recs.append(
                    Recommendation(
                        priority="low",
                        icon="📊",
                        title="Revisa tu cartera",
                        text="Hay transacciones registradas pero no se detectan posiciones activas.",
                        action="Abrir Portfolio → Cartera",
                        source="stock",
                    )
                )

        # Real estate: si el módulo está habilitado y hay propiedades sin valoración estimada (placeholder).
        if "real_estate" in enabled:
            prop = RealEstateProperty.query.filter_by(user_id=user_id).first()
            if prop is not None:
                # No tenemos un campo explícito aquí; dejamos ejemplo para ampliar.
                pass

        # ---- Deduplicación + orden ----
        seen = set()
        deduped: list[Recommendation] = []
        for r in recs:
            key = (r.title.strip().lower(), r.text.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)

        pr_order = {"high": 0, "medium": 1, "low": 2}
        deduped.sort(key=lambda x: (pr_order.get(x.priority, 9)))

        return [r.as_dict() for r in deduped[:8]]

