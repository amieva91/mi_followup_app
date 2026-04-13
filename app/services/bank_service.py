"""
Servicio para gestión de cuentas bancarias y saldos
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from app.models import Bank, BankBalance


class BankService:
    @staticmethod
    def get_banks(user_id):
        """Lista de bancos del usuario ordenados por nombre"""
        return Bank.query.filter_by(user_id=user_id).order_by(Bank.name).all()

    @staticmethod
    def get_total_cash_by_month(user_id, year, month):
        """Total de efectivo (suma de todos los bancos) para un mes"""
        total = db.session.query(db.func.sum(BankBalance.amount)).filter(
            BankBalance.user_id == user_id,
            BankBalance.year == year,
            BankBalance.month == month
        ).scalar()
        return float(total or 0)

    @staticmethod
    def get_balances_for_month(user_id, year, month):
        """Dict {bank_id: amount} para el mes dado"""
        balances = BankBalance.query.filter_by(
            user_id=user_id, year=year, month=month
        ).all()
        return {b.bank_id: float(b.amount) for b in balances}

    @staticmethod
    def get_cash_evolution(user_id, months=12):
        """Lista de {month_label, total} ordenada cronológicamente"""
        today = date.today()
        result = []
        for i in range(months - 1, -1, -1):
            d = today - relativedelta(months=i)
            total = BankService.get_total_cash_by_month(user_id, d.year, d.month)
            month_label = d.strftime('%b %Y')
            result.append({'year': d.year, 'month': d.month, 'month_label': month_label, 'total': total})
        return result

    @staticmethod
    def save_balances(user_id, year, month, balances_dict):
        """
        balances_dict: {bank_id: amount}
        Crea o actualiza BankBalance para cada banco
        """
        banks = BankService.get_banks(user_id)
        bank_ids = {b.id for b in banks}

        for bank_id, amount in balances_dict.items():
            if bank_id not in bank_ids:
                continue
            amount = float(amount) if amount is not None and amount != '' else 0.0
            balance = BankBalance.query.filter_by(
                user_id=user_id, bank_id=bank_id, year=year, month=month
            ).first()
            if balance:
                balance.amount = amount
            else:
                balance = BankBalance(
                    user_id=user_id,
                    bank_id=bank_id,
                    year=year,
                    month=month,
                    amount=amount
                )
                db.session.add(balance)
        db.session.commit()

        # Si se edita un mes anterior al actual, el histórico del dashboard queda 'congelado'
        # en cache. Marcamos full rebuild para que se regenere summary.history (cash incluido).
        today = date.today()
        if (int(year), int(month)) != (today.year, today.month):
            try:
                from app.models.dashboard_summary_cache import DashboardSummaryCache

                cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
                if cache and cache.cached_data:
                    data = dict(cache.cached_data)
                    meta = dict(data.get('meta') or {})
                    meta['needs_full_rebuild'] = True
                    meta['needs_full_rebuild_reason'] = 'bank_balances_hist_changed'
                    data['meta'] = meta
                    cache.cached_data = data
                    db.session.commit()
            except Exception:
                # No bloquear guardado de bancos por fallos de cache
                db.session.rollback()
