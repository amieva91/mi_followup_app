#!/usr/bin/env python3
"""Verifica reconciliación mes a mes (ajuste = c_prev + income - c_cur - exp_reg). Uso en VM: ver abajo."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from dateutil.relativedelta import relativedelta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--months", type=int, default=12)
    args = parser.parse_args()

    os.environ.setdefault("FLASK_APP", "run.py")
    os.environ.setdefault("FLASK_ENV", "production")

    from app import create_app
    from app.models import User
    from app.services.bank_service import BankService
    from app.services.reconciliation_service import (
        _get_prev_month,
        _has_any_balance_for_month,
        get_adjustment_for_month,
        get_expense_total_for_month,
        get_income_total_for_month,
    )

    app = create_app()
    with app.app_context():
        u = User.query.filter_by(email=args.email.strip()).first()
        if not u:
            print("USER_NOT_FOUND", args.email, file=sys.stderr)
            return 1
        uid = u.id
        today = date.today()
        n = args.months
        print(f"user_id={uid} email={args.email!r} today={today.isoformat()} últimos {n} meses")
        print()
        hdr = (
            f"{'ym':>8} {'c_prev':>10} {'c_cur':>10} {'income':>10} {'exp_reg':>10} "
            f"{'real_exp':>10} {'adj_fn':>10} {'adj_re':>10} {'ok':>4} {'ing_aj':>8}"
        )
        print(hdr)
        print("-" * len(hdr))

        mismatches = []
        none_bank = []

        for i in range(n - 1, -1, -1):
            d = today - relativedelta(months=i)
            y, m = d.year, d.month
            py, pm = _get_prev_month(y, m)
            key = f"{y}-{m:02d}"

            if not _has_any_balance_for_month(uid, py, pm) or not _has_any_balance_for_month(
                uid, y, m
            ):
                none_bank.append(key)
                print(f"{key:>8}  (sin BankBalance en mes previo o actual — ajuste N/A)")
                continue

            c_prev = BankService.get_total_cash_by_month(uid, py, pm)
            c_cur = BankService.get_total_cash_by_month(uid, y, m)
            inc = get_income_total_for_month(uid, y, m)
            exp_r = get_expense_total_for_month(uid, y, m)
            real = c_prev + inc - c_cur
            adj_fn = get_adjustment_for_month(uid, y, m)
            adj_re = round(real - exp_r, 2)
            ok = adj_fn is not None and abs(adj_fn - adj_re) < 0.02
            ing_aj = round(abs(adj_fn), 2) if adj_fn is not None and adj_fn < 0 else 0.0
            flag = "OK" if ok else "BAD"
            if not ok:
                mismatches.append((key, adj_fn, adj_re))
            adj_fn_s = f"{adj_fn:.2f}" if adj_fn is not None else "None"
            print(
                f"{key:>8} {c_prev:10.2f} {c_cur:10.2f} {inc:10.2f} {exp_r:10.2f} {real:10.2f} "
                f"{adj_fn_s:>10} {adj_re:10.2f} {flag:>4} {ing_aj:8.2f}"
            )

        print()
        print(
            "ing_aj = línea sintética ingreso ‘no registrado’ (|ajuste| si ajuste < 0). "
            "Si ajuste > 0 es gasto no registrado (no entra en ingresos sintéticos)."
        )
        if none_bank:
            print("Sin datos bancarios completos:", ", ".join(none_bank))
        if mismatches:
            print("DISCREPANCIAS:", mismatches, file=sys.stderr)
            return 2
        print("OK: get_adjustment_for_month coincide con la fórmula en todos los meses con banco.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
