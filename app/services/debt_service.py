"""
Servicio para gestión de planes de deuda y cuotas
"""
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from app import db
from app.models import DebtPlan, Expense, ExpenseCategory, Income
from sqlalchemy import extract, func, or_


class DebtService:
    """Servicio para planes de deuda"""

    @staticmethod
    def create_debt_plan(user_id, name, total_amount, months, start_date, category_id, notes=None):
        """
        Crea un DebtPlan y genera los Expense (cuotas) correspondientes.
        
        Returns:
            DebtPlan creado o None si hay error
        """
        if months <= 0 or total_amount <= 0:
            return None
        
        monthly_payment = round(total_amount / months, 2)
        plan = DebtPlan(
            user_id=user_id,
            category_id=category_id,
            name=name,
            total_amount=total_amount,
            months=months,
            start_date=start_date,
            status='ACTIVE',
            notes=notes
        )
        db.session.add(plan)
        db.session.flush()

        current_date = start_date
        for i in range(months):
            desc = f"Cuota {i + 1}/{months} - {name}"
            expense = Expense(
                user_id=user_id,
                category_id=category_id,
                amount=monthly_payment,
                description=desc,
                date=current_date,
                notes=notes,
                is_recurring=False,
                debt_plan_id=plan.id
            )
            db.session.add(expense)
            current_date = current_date + relativedelta(months=1)

        db.session.commit()
        return plan

    @staticmethod
    def update_debt_plan(plan_id, user_id, name, total_amount, months, start_date, category_id, notes=None):
        """
        Actualiza un plan de deuda y sincroniza las cuotas (Expense) correspondientes.
        La edición es como si el plan se creara de nuevo: TODAS las cuotas (pasadas y futuras)
        se actualizan con la nueva cuota mensual (total/meses).
        - name, category_id, notes: se actualizan en plan y en todas las cuotas.
        - total_amount, months: nueva cuota = total/meses aplicada a TODAS las cuotas.
        - start_date: se desplazan las fechas de las cuotas.
        Returns True si ok, False si error.
        """
        plan = DebtPlan.query.filter_by(id=plan_id, user_id=user_id).first_or_404()
        today = date.today()
        old_start = plan.start_date

        past_expenses = Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date <= today
        ).order_by(Expense.date.asc()).all()
        future_expenses = Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date > today
        ).order_by(Expense.date.asc()).all()

        if months < len(past_expenses):
            return False

        plan.name = name
        plan.total_amount = round(total_amount, 2)
        plan.months = months
        plan.start_date = start_date
        plan.category_id = category_id
        plan.notes = notes

        # Nueva cuota mensual uniforme (como si se creara el plan de nuevo)
        new_monthly = round(total_amount / months, 2)
        past_count = len(past_expenses)
        future_count = months - past_count

        # 1. Actualizar category_id, notes y amounts en TODAS las cuotas existentes
        all_expenses = past_expenses + future_expenses
        for exp in all_expenses:
            exp.category_id = category_id
            if not (exp.notes and 'Pago anticipado' in exp.notes):
                exp.notes = notes

        # 2. Si cambió start_date: desplazar fechas
        if start_date != old_start:
            delta = relativedelta(start_date, old_start)
            for exp in all_expenses:
                exp.date = exp.date + delta

        # 3. Actualizar importes de TODAS las cuotas a la nueva cuota (última con ajuste por redondeo)
        for i, exp in enumerate(all_expenses):
            if i + 1 < months:
                exp.amount = new_monthly
            else:
                exp.amount = round(total_amount - new_monthly * (months - 1), 2)

        # 4. Eliminar cuotas futuras sobrantes o añadir las que falten
        for exp in future_expenses:
            db.session.delete(exp)

        if future_count > 0:
            last_date = past_expenses[-1].date + relativedelta(months=1) if past_expenses else start_date
            for i in range(future_count):
                amount = new_monthly if i < future_count - 1 else round(total_amount - new_monthly * (months - 1), 2)
                desc = f"Cuota {past_count + i + 1}/{months} - {name}"
                exp = Expense(
                    user_id=user_id,
                    category_id=category_id,
                    amount=amount,
                    description=desc,
                    date=last_date,
                    notes=notes,
                    is_recurring=False,
                    debt_plan_id=plan.id
                )
                db.session.add(exp)
                last_date = last_date + relativedelta(months=1)
        elif past_expenses and months == past_count:
            plan.status = 'PAID_OFF'

        # 5. Actualizar descripciones (respetar Pago Anticipado en la última pasada)
        for i, exp in enumerate(past_expenses, 1):
            is_advance = exp.notes and 'Pago anticipado' in exp.notes
            if is_advance and i == len(past_expenses):
                exp.description = f"Cuota {i}/{months} - {name} - Pago Anticipado"
            else:
                exp.description = f"Cuota {i}/{months} - {name}"

        db.session.commit()
        return True

    @staticmethod
    def _sync_plan_from_remaining_expenses(plan):
        """Actualiza total_amount, months del plan y descripciones de cuotas según los Expense restantes."""
        remaining = Expense.query.filter_by(
            debt_plan_id=plan.id
        ).order_by(Expense.date.asc()).all()
        if not remaining:
            plan.status = 'CANCELLED'
            return
        total = sum(exp.amount for exp in remaining)
        count = len(remaining)
        plan.total_amount = round(total, 2)
        plan.months = count
        for i, exp in enumerate(remaining, 1):
            # Preservar " - Pago Anticipado" en la última cuota si es pago anticipado
            is_advance = exp.notes and 'Pago anticipado' in exp.notes
            if is_advance and i == count:
                exp.description = f"Cuota {i}/{count} - {plan.name} - Pago Anticipado"
            else:
                exp.description = f"Cuota {i}/{count} - {plan.name}"

    @staticmethod
    def cancel_plan(plan_id, user_id, delete_future_only=False, cutoff_date=None):
        """
        Cancela un plan de deuda.
        
        Args:
            delete_future_only: Si True, elimina solo cuotas a partir del cutoff.
                               Si False, elimina todo el plan y todas las cuotas.
            cutoff_date: Fecha a partir de la cual eliminar (inclusive).
                        Si None y delete_future_only, usa date.today().
        """
        plan = DebtPlan.query.filter_by(id=plan_id, user_id=user_id).first_or_404()
        from_date = cutoff_date if cutoff_date is not None else date.today()

        if delete_future_only:
            future_expenses = Expense.query.filter(
                Expense.debt_plan_id == plan_id,
                Expense.date >= from_date
            ).all()
            for exp in future_expenses:
                db.session.delete(exp)
            # Actualizar plan y descripciones de cuotas restantes
            DebtService._sync_plan_from_remaining_expenses(plan)
            # Si no quedan cuotas futuras, el plan está completado
            today = date.today()
            has_future = Expense.query.filter(
                Expense.debt_plan_id == plan_id,
                Expense.date > today
            ).first() is not None
            if not has_future:
                plan.status = 'PAID_OFF'
            db.session.commit()
            return len(future_expenses)
        else:
            Expense.query.filter_by(debt_plan_id=plan_id).delete()
            db.session.delete(plan)
            db.session.commit()
            return -1

    @staticmethod
    def mark_as_paid_off(plan_id, user_id):
        """
        Paga anticipadamente: crea un gasto con el importe restante en el mes actual,
        elimina las cuotas futuras, actualiza las descripciones de las cuotas pasadas
        y sincroniza el plan.
        """
        plan = DebtPlan.query.filter_by(id=plan_id, user_id=user_id).first_or_404()
        today = date.today()

        future_expenses = Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date > today
        ).order_by(Expense.date.asc()).all()

        remaining_amount = sum(exp.amount for exp in future_expenses)
        deleted_count = len(future_expenses)

        # Cuotas pasadas (ya pagadas)
        past_expenses = Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date <= today
        ).order_by(Expense.date.asc()).all()

        past_count = len(past_expenses)
        total_installments = past_count + 1  # las pasadas + el pago anticipado

        # Eliminar cuotas futuras
        for exp in future_expenses:
            db.session.delete(exp)

        # Actualizar descripciones de cuotas pasadas: Cuota 1/X - Plan, Cuota 2/X - Plan...
        for i, exp in enumerate(past_expenses, 1):
            exp.description = f"Cuota {i}/{total_installments} - {plan.name}"

        # Crear gasto único con el importe restante en el mes actual
        if remaining_amount > 0:
            lump_expense = Expense(
                user_id=user_id,
                category_id=plan.category_id,
                amount=round(remaining_amount, 2),
                description=f"Cuota {total_installments}/{total_installments} - {plan.name} - Pago Anticipado",
                date=today,
                notes=f"Pago anticipado del plan de deuda (restaban {deleted_count} cuotas)",
                is_recurring=False,
                debt_plan_id=plan.id
            )
            db.session.add(lump_expense)

        plan.status = 'PAID_OFF'
        DebtService._sync_plan_from_remaining_expenses(plan)
        db.session.commit()
        return deleted_count

    @staticmethod
    def restructure_plan(plan_id, user_id, new_monthly_payment=None, new_months=None):
        """
        Reestructura un plan: cambia la cuota mensual o los meses restantes.
        Total pendiente se mantiene. Pasar new_monthly_payment O new_months.
        Returns: (new_months, new_payment, success) o (0, 0, False) si error.
        """
        import math
        plan = DebtPlan.query.filter_by(id=plan_id, user_id=user_id).first_or_404()
        if plan.status != 'ACTIVE':
            return 0, 0, False

        today = date.today()
        future_expenses = Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date > today
        ).order_by(Expense.date).all()

        if not future_expenses:
            return 0, 0, False

        remaining_amount = round(sum(exp.amount for exp in future_expenses), 2)

        if new_months is not None and new_months >= 1:
            new_months = int(new_months)
            new_monthly_payment = round(remaining_amount / new_months, 2)
        elif new_monthly_payment and new_monthly_payment > 0:
            new_months = max(1, math.ceil(remaining_amount / new_monthly_payment))
        else:
            return 0, 0, False
        first_future_date = future_expenses[0].date

        # Eliminar cuotas futuras
        for exp in future_expenses:
            db.session.delete(exp)

        # Calcular nuevas cuotas
        new_months = max(1, math.ceil(remaining_amount / new_monthly_payment))
        amounts = [round(new_monthly_payment, 2)] * (new_months - 1)
        last_amount = round(remaining_amount - sum(amounts), 2)
        amounts.append(last_amount)

        past_count = Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date <= today
        ).count()

        current_date = first_future_date
        for i, amt in enumerate(amounts):
            desc = f"Cuota {past_count + i + 1}/{plan.months} - {plan.name}"
            exp = Expense(
                user_id=user_id,
                category_id=plan.category_id,
                amount=amt,
                description=desc,
                date=current_date,
                notes=plan.notes,
                is_recurring=False,
                debt_plan_id=plan.id
            )
            db.session.add(exp)
            current_date = current_date + relativedelta(months=1)

        DebtService._sync_plan_from_remaining_expenses(plan)
        db.session.commit()
        return new_months, new_monthly_payment, True

    @staticmethod
    def get_monthly_debt_schedule(user_id, months_ahead=12, months_back=12, include_by_plan=True):
        """
        Obtiene el calendario de pagos de deuda por mes (pasados y futuros).
        
        Args:
            months_ahead: Meses futuros a incluir.
            months_back: Meses pasados a incluir (cuotas ya pagadas).
            include_by_plan: Si True, incluye desglose por plan para gráfico stacked.
        
        Returns:
            list of dict con month_key, month_label, amount, y opcionalmente by_plan, plan_colors, plan_ids.
        """
        today = date.today()
        start = today - relativedelta(months=months_back)
        end = today + relativedelta(months=months_ahead)

        plans = DebtPlan.query.filter_by(
            user_id=user_id,
            status='ACTIVE'
        ).all()

        # Total por mes
        schedule_total = defaultdict(float)
        # Por plan: {plan_id: {month_key: amount}}
        schedule_by_plan = defaultdict(lambda: defaultdict(float))

        # Incluir también planes PAID_OFF/CANCELLED para histórico (solo cuotas pasadas)
        all_plans = DebtPlan.query.filter_by(user_id=user_id).all()

        for plan in all_plans:
            expenses = Expense.query.filter(
                Expense.debt_plan_id == plan.id,
                Expense.date >= start,
                Expense.date < end + relativedelta(months=1)
            ).all()
            for exp in expenses:
                key = exp.date.strftime('%Y-%m')
                schedule_total[key] += exp.amount
                schedule_by_plan[plan.id][key] += exp.amount

        _MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')

        result = []
        current = start.replace(day=1)
        end_date = end + relativedelta(months=1)
        plan_colors = {}
        COLORS = [
            'rgba(59, 130, 246, 0.8)',   # blue
            'rgba(16, 185, 129, 0.8)',   # green
            'rgba(245, 158, 11, 0.8)',   # amber
            'rgba(139, 92, 246, 0.8)',   # purple
            'rgba(236, 72, 153, 0.8)',   # pink
            'rgba(20, 184, 166, 0.8)',   # teal
        ]
        for i, plan in enumerate(plans):
            plan_colors[plan.id] = COLORS[i % len(COLORS)]

        while current < end_date:
            key = current.strftime('%Y-%m')
            label = f"{_MESES[current.month - 1]} {current.year}"
            row = {
                'month_key': key,
                'month_label': label,
                'amount': round(schedule_total.get(key, 0), 2)
            }
            if include_by_plan and plans:
                row['by_plan'] = {
                    str(pid): round(schedule_by_plan[pid].get(key, 0), 2)
                    for pid in [p.id for p in plans]
                }
            result.append(row)
            current = current + relativedelta(months=1)

        if include_by_plan:
            return {
                'months': result,
                'plan_colors': {str(pid): plan_colors.get(pid, COLORS[0]) for pid in [p.id for p in plans]},
                'plan_ids': [p.id for p in plans],
                'plan_names': {str(p.id): p.name for p in plans}
            }
        return result

    @staticmethod
    def get_total_debt_remaining(user_id):
        """Total de deuda pendiente de pago (solo cuotas futuras)."""
        today = date.today()
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.debt_plan_id.isnot(None),
            Expense.date > today
        ).scalar()
        return float(total or 0)

    @staticmethod
    def get_active_plans(user_id):
        """Lista de planes activos del usuario, ordenados por fecha de fin (los que terminan antes primero)."""
        plans = DebtPlan.query.filter_by(
            user_id=user_id,
            status='ACTIVE'
        ).all()
        return sorted(plans, key=lambda p: p.start_date + relativedelta(months=p.months))

    @staticmethod
    def get_inactive_plans(user_id):
        """Lista de planes PAID_OFF y CANCELLED, ordenados por fecha de inicio (más recientes primero)."""
        plans = DebtPlan.query.filter(
            DebtPlan.user_id == user_id,
            or_(DebtPlan.status == 'PAID_OFF', DebtPlan.status == 'CANCELLED')
        ).order_by(DebtPlan.start_date.desc()).all()
        return plans

    @staticmethod
    def get_months_paid(plan_id):
        """Cuántas cuotas ya vencidas tiene el plan (date <= hoy)."""
        today = date.today()
        return Expense.query.filter(
            Expense.debt_plan_id == plan_id,
            Expense.date <= today
        ).count()

    @staticmethod
    def get_income_last_12_months(user_id):
        """
        Total de ingresos de los últimos 12 meses.
        Returns: (total, months_with_data, is_full_year)
        """
        today = date.today()
        start = today - relativedelta(months=12)
        total = Income.get_total_by_period(user_id, start, today)

        # Contar meses distintos con datos (compatible SQLite y PostgreSQL)
        try:
            subq = db.session.query(
                extract('year', Income.date),
                extract('month', Income.date)
            ).filter(
                Income.user_id == user_id,
                Income.date >= start,
                Income.date <= today
            ).distinct()
            months_with_data = subq.count()
        except Exception:
            months_with_data = 12 if total else 0

        return float(total or 0), months_with_data, months_with_data >= 12

    @staticmethod
    def get_debt_limit_info(user, debt_limit_percent=None):
        """
        Información para el límite de endeudamiento.
        
        Returns:
            dict con: avg_monthly_income, max_monthly_debt, max_yearly_debt,
                     current_monthly_debt, margin, is_full_year
        """
        limit_pct = debt_limit_percent if debt_limit_percent is not None else (user.debt_limit_percent or 35.0)
        total_income, months_with_data, is_full_year = DebtService.get_income_last_12_months(user.id)

        avg_monthly_income = total_income / 12 if total_income else 0
        max_monthly_debt = round(avg_monthly_income * (limit_pct / 100), 2)
        max_yearly_debt = round(max_monthly_debt * 12, 2)

        schedule_result = DebtService.get_monthly_debt_schedule(user.id, months_ahead=12)
        if isinstance(schedule_result, dict):
            months = schedule_result.get('months', [])
        else:
            months = schedule_result if isinstance(schedule_result, list) else []
        # Solo usar elementos dict con clave 'amount' (defensivo ante formatos inesperados)
        current_monthly_debt = max(
            (s.get('amount', 0) for s in months if isinstance(s, dict)),
            default=0
        )

        margin = round(max_monthly_debt - current_monthly_debt, 2)

        return {
            'avg_monthly_income': avg_monthly_income,
            'max_monthly_debt': max_monthly_debt,
            'max_yearly_debt': max_yearly_debt,
            'current_monthly_debt': current_monthly_debt,
            'margin': margin,
            'is_full_year': is_full_year,
            'debt_limit_percent': limit_pct,
            'total_income_12m': total_income,
        }
