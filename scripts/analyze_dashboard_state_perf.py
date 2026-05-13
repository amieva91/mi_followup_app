#!/usr/bin/env python3
"""
Agrega tiempos [perf] del log para GET /dashboard/state y recompute_current_from_cache.

Uso (en la VM o local, con el log de la app):
  python3 scripts/analyze_dashboard_state_perf.py --log /var/www/followup/logs/followup.log
  python3 scripts/analyze_dashboard_state_perf.py --log logs/followup.log --user-id 3 --tail 80000

Salida: media y mediana de step_ms por paso (solo líneas con route indicada).
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import defaultdict
from typing import DefaultDict, List, Tuple

# 2026-05-13 20:09:23,781 - followup.perf - INFO - [perf] route=... user_id=... step=... step_ms=... total_ms=...
# route puede contener espacios (p. ej. "GET /dashboard/state")
LINE_RE = re.compile(
    r"\[perf\] route=(?P<route>.+?)\s+user_id=(?P<uid>\S+)\s+step=(?P<step>\S+)\s+"
    r"step_ms=(?P<sm>[\d.]+)\s+total_ms=(?P<tm>[\d.]+)"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Media/mediana de [perf] para dashboard state")
    p.add_argument("--log", default="logs/followup.log", help="Ruta al followup.log")
    p.add_argument("--tail", type=int, default=120_000, help="Leer solo las últimas N chars del fichero")
    p.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Filtrar solo este user_id (recomendado si hay varias cuentas)",
    )
    p.add_argument(
        "--routes",
        default="GET /dashboard/state,recompute_current_from_cache",
        help="Lista CSV de route= a incluir",
    )
    return p.parse_args()


def tail_text(path: str, max_chars: int) -> str:
    with open(path, "rb") as f:
        if max_chars <= 0:
            return f.read().decode("utf-8", errors="replace")
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - max_chars)
        f.seek(start)
        return f.read().decode("utf-8", errors="replace")


def main() -> int:
    args = parse_args()
    routes_want = {r.strip() for r in args.routes.split(",") if r.strip()}
    buckets: DefaultDict[Tuple[str, str], List[float]] = defaultdict(list)

    try:
        text = tail_text(args.log, args.tail)
    except OSError as e:
        print(f"No se pudo leer {args.log}: {e}", file=sys.stderr)
        return 1

    for line in text.splitlines():
        if "[perf]" not in line:
            continue
        m = LINE_RE.search(line)
        if not m:
            continue
        route = m.group("route")
        uid_s = m.group("uid")
        step = m.group("step")
        sm = float(m.group("sm"))
        if route not in routes_want:
            continue
        if args.user_id is not None:
            try:
                if int(uid_s) != args.user_id:
                    continue
            except ValueError:
                continue
        buckets[(route, step)].append(sm)

    if not buckets:
        print("No hay líneas [perf] coincidentes (revisa --log, --tail, --user-id, --routes).")
        return 0

    # Ordenar: primero state (orden de aparición en código), luego recompute
    state_order = [
        "enter",
        "cache_row_query",
        "exit_no_cache",
        "recompute_current_from_cache",
        "exit_recompute_none",
        "cache_get_after_recompute",
        "exit_cache_none",
        "price_updates_since",
        "jsonify_response",
    ]
    recompute_order = [
        "enter",
        "cache_row_loaded",
        "needs_full_rebuild_start",
        "needs_full_rebuild_get_summary_done",
        "needs_full_rebuild_cache_set",
        "history_resolved",
        "after_breakdown_and_details",
        "after_savings_through_health",
        "after_recommendations_indices_commodities",
        "after_day_change",
        "after_align_last_history",
        "before_db_commit",
        "exit_ok",
    ]

    def dump_section(title: str, route: str, order: List[str]) -> None:
        print(title)
        print(f"{'step':<48} {'n':>6} {'mean_ms':>10} {'median_ms':>11} {'min':>9} {'max':>9}")
        print("-" * 96)
        for step in order:
            key = (route, step)
            vals = buckets.get(key)
            if not vals:
                continue
            mean_v = statistics.mean(vals)
            med_v = statistics.median(vals)
            print(
                f"{step:<48} {len(vals):>6} {mean_v:>10.1f} {med_v:>11.1f} "
                f"{min(vals):>9.1f} {max(vals):>9.1f}"
            )
        listed = set(order)
        extras = [(s, v) for (r, s), v in buckets.items() if r == route and s not in listed]
        for step, vals in sorted(extras, key=lambda x: x[0]):
            mean_v = statistics.mean(vals)
            med_v = statistics.median(vals)
            print(
                f"{step:<48} {len(vals):>6} {mean_v:>10.1f} {med_v:>11.1f} "
                f"{min(vals):>9.1f} {max(vals):>9.1f}"
            )
        print()

    if "GET /dashboard/state" in routes_want:
        dump_section("=== GET /dashboard/state (step_ms entre marcas consecutivas) ===", "GET /dashboard/state", state_order)
    if "recompute_current_from_cache" in routes_want:
        dump_section(
            "=== recompute_current_from_cache (llamado desde /dashboard/state) ===",
            "recompute_current_from_cache",
            recompute_order,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
