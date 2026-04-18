#!/usr/bin/env python3
"""Desglose de reconciliación para un mes concreto (saldos por banco, I/G, broker)."""
from __future__ import annotations

import argparse
import os
import sys
def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    args = p.parse_args()

    os.environ.setdefault("FLASK_APP", "run.py")
    os.environ.setdefault("FLASK_ENV", "production")

    from sqlalchemy import extract

    from app import create_app, db
    from app.models import (
        Bank,
        BankBalance,
        Expense,
        ExpenseCategory,
        Income,
        IncomeCategory,
        Transaction,
        User,
    )
    from app.services.bank_service import BankService
    from app.services.broker_sync_service import (
        _broker_account_ids,
        get_broker_deposits_total_by_month,
        get_broker_withdrawals_by_month,
    )
    from app.services.currency_service import convert_to_eur
    from app.services.reconciliation_service import (
        _get_prev_month,
        _month_range,
        get_adjustment_for_month,
        get_expense_total_for_month,
        get_income_total_for_month,
    )

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=args.email.strip()).first()
        if not user:
            print("USER_NOT_FOUND", args.email, file=sys.stderr)
            return 1
        uid = user.id
        y, m = args.year, args.month
        py, pm = _get_prev_month(y, m)
        start, end = _month_range(y, m)

        print(f"Usuario id={uid} {args.email!r}")
        print(f"Mes objetivo: {y}-{m:02d} | Mes previo (caja inicial): {py}-{pm:02d}")
        print()

        # Saldos por banco
        banks = Bank.query.filter_by(user_id=uid).order_by(Bank.name).all()
        print("=== Saldos por banco (BankBalance) ===")
        sum_prev = 0.0
        sum_cur = 0.0
        for b in banks:
            bp = BankBalance.query.filter_by(
                user_id=uid, bank_id=b.id, year=py, month=pm
            ).first()
            bc = BankBalance.query.filter_by(
                user_id=uid, bank_id=b.id, year=y, month=m
            ).first()
            ap = float(bp.amount) if bp else None
            ac = float(bc.amount) if bc else None
            sum_prev += ap if ap is not None else 0.0
            sum_cur += ac if ac is not None else 0.0
            print(
                f"  {b.name:20}  {py}-{pm:02d}: {ap if ap is not None else '—':>12}  |  "
                f"{y}-{m:02d}: {ac if ac is not None else '—':>12}"
            )
        print(f"  {'TOTAL suma filas':20}  {sum_prev:12.2f}  |  {sum_cur:12.2f}")
        svc_prev = BankService.get_total_cash_by_month(uid, py, pm)
        svc_cur = BankService.get_total_cash_by_month(uid, y, m)
        print(f"  {'BankService total':20}  {svc_prev:12.2f}  |  {svc_cur:12.2f}")
        print()

        inc_tot = get_income_total_for_month(uid, y, m)
        exp_tot = get_expense_total_for_month(uid, y, m)
        adj = get_adjustment_for_month(uid, y, m)
        real = svc_prev + inc_tot - svc_cur
        print("=== Agregados reconciliación ===")
        print(f"  cash_prev:           {svc_prev:,.2f}")
        print(f"  cash_current:        {svc_cur:,.2f}")
        print(f"  Δ caja (cur − prev): {svc_cur - svc_prev:,.2f}")
        print(f"  ingresos (recon):    {inc_tot:,.2f}")
        print(f"  gastos registrados:  {exp_tot:,.2f}")
        print(f"  gasto implícito:     {real:,.2f}  (= prev + ing − cur)")
        print(f"  ajuste:              {adj}  (= implícito − gastos_reg)")
        print()

        # Ingresos tabla
        incomes = (
            Income.query.filter(
                Income.user_id == uid, Income.date >= start, Income.date <= end
            )
            .order_by(Income.date, Income.id)
            .all()
        )
        print(f"=== Incomes tabla ({len(incomes)} filas) {start} .. {end} ===")
        inc_sum = 0.0
        for r in incomes:
            cat = db.session.get(IncomeCategory, r.category_id)
            cn = cat.name if cat else "?"
            inc_sum += float(r.amount or 0)
            print(f"  {r.date}  {cn:15}  {r.amount:10.2f}  {r.description!r}")
        print(f"  Suma (todas categorías en tabla): {inc_sum:,.2f}")
        br_w = get_broker_withdrawals_by_month(uid, y, m)
        print(f"  Broker WITHDRAWAL (suma):         {br_w:,.2f}")
        print(f"  Total ingresos recon (tabla excl. Stock/Ajustes + broker): {inc_tot:,.2f}")
        print()

        exps = (
            Expense.query.filter(
                Expense.user_id == uid, Expense.date >= start, Expense.date <= end
            )
            .order_by(Expense.date, Expense.id)
            .all()
        )
        print(f"=== Expenses tabla ({len(exps)} filas) ===")
        for r in exps:
            cat = db.session.get(ExpenseCategory, r.category_id)
            cn = cat.name if cat else "?"
            print(f"  {r.date}  {cn:15}  {r.amount:10.2f}  {r.description!r}")
        br_d = get_broker_deposits_total_by_month(uid, y, m)
        print(f"  Broker DEPOSIT: {br_d:,.2f}")
        print()

        acc_ids = [x[0] for x in _broker_account_ids(uid)]
        if acc_ids:
            w_tx = (
                Transaction.query.filter(
                    Transaction.user_id == uid,
                    Transaction.account_id.in_(acc_ids),
                    Transaction.transaction_type == "WITHDRAWAL",
                    extract("year", Transaction.transaction_date) == y,
                    extract("month", Transaction.transaction_date) == m,
                )
                .order_by(Transaction.transaction_date, Transaction.id)
                .all()
            )
            print(f"=== WITHDRAWAL broker ({len(w_tx)}) ===")
            for t in w_tx:
                eur = convert_to_eur(abs(t.amount), t.currency)
                print(
                    f"  {t.transaction_date}  id={t.id}  {eur:10.2f} EUR  "
                    f"raw={t.amount} {t.currency}"
                )

        print()
        print(
            "=== Interpretación ===\n"
            "  Ajuste negativo ⇒ la caja subió más de lo explicable con ingresos registrados\n"
            "  (o bajó menos) ⇒ ‘ingreso no registrado’.\n"
            "  Revisa: cuentas sin saldo en mes previo, traspasos, primer mes con todos los bancos, errores de cifra."
        )
        return 0


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    raise SystemExit(main())
