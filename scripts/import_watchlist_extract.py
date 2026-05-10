#!/usr/bin/env python3
"""
Importa bloques de texto con formato FollowUp / Gem en la watchlist (campos manuales, origen ``ai``).

Formato esperado (modo entre corchetes en mayúsculas o minúsculas):

    === ONDS [GENERAL] ===
    next_earnings_date: 2026-05-14
    per_ntm: -1.2
    ...

    === HSBK [BANKS] ===
    next_earnings_date: 2026-05-18
    price_to_book: 1.18
    ...

    === O [REALESTATE] ===
    ffo_per_share: 4.28
    ...

    === FUENTES ===
    * [título](https://...)

La sección ``=== FUENTES ===`` (con o sin lista markdown) no se importa; puede ir al final del fichero.
El modo del bloque no filtra campos: deben usarse los identificadores que acepta la app.

Solo escribe ``next_earnings_date`` si viene en el bloque del ticker; si falta, no borra la fecha ya guardada.

Uso (raíz del repo, venv activo):

    python scripts/import_watchlist_extract.py --user-id 3 /ruta/datos.txt
    python scripts/import_watchlist_extract.py --user-id 3 --dry-run /ruta/datos.txt
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Acepta GENERAL, BANKS, REALESTATE, general, etc.
BLOCK_RE = re.compile(r"^===\s+(\S+)\s+\[([^\]]+)\]\s*===\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^([a-z][a-z0-9_]*)\s*:\s*(.*)$", re.I)

FUENTES_LINE_RE = re.compile(r"^===\s*FUENTES\s*===\s*$", re.I)


def norm_symbol(sym: str) -> str:
    s = (sym or "").upper().strip()
    for suf in (".HK", ".L", "-HK"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def parse_extract_file(text: str) -> dict[str, dict[str, str]]:
    """
    Por ticker, último bloque gana si hay duplicados.
    Ignora bloques cuyo nombre sea FUENTES (si algún día usara [x]).
    Dentro de cada bloque, deja de leer al llegar a ``=== FUENTES ===`` sin modo (pie del informe).
    """
    matches = list(BLOCK_RE.finditer(text))
    out: dict[str, dict[str, str]] = {}
    for i, m in enumerate(matches):
        ticker = m.group(1).strip()
        if ticker.upper() == "FUENTES":
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]
        row = out.setdefault(ticker, {})
        for line in chunk.splitlines():
            line_raw = line.strip()
            if not line_raw:
                continue
            if FUENTES_LINE_RE.match(line_raw.strip()):
                break
            fm = FIELD_RE.match(line_raw)
            if not fm:
                continue
            k = fm.group(1).lower()
            v = fm.group(2).strip()
            if v in ("", "—", "-"):
                continue
            row[k] = v
    return out


def _parse_manual_date(raw: str):
    raw = raw.strip()
    iso_m = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    if iso_m:
        try:
            return datetime.strptime(iso_m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    from dateutil.parser import parse as du_parse

    return du_parse(raw, dayfirst=False).date()


def coerce_value(key: str, raw: str):
    from app.models.watchlist import WATCHLIST_MANUAL_DATE_KEYS, WATCHLIST_MANUAL_STRING_KEYS

    raw = raw.strip()
    if key in WATCHLIST_MANUAL_DATE_KEYS:
        return _parse_manual_date(raw)
    if key in WATCHLIST_MANUAL_STRING_KEYS:
        return str(raw)[:32]
    return float(raw.replace(",", ".").replace(" ", ""))


def build_watchlist_index(user_id: int) -> dict[str, list]:
    from app.models import Asset, Watchlist

    items = (
        Watchlist.query.filter_by(user_id=user_id).join(Asset, Watchlist.asset_id == Asset.id).all()
    )
    by_norm: dict[str, list] = {}
    for wl in items:
        sym = wl.asset.symbol or ""
        n = norm_symbol(sym)
        by_norm.setdefault(n, []).append((wl, wl.asset))
    return by_norm


def resolve_watchlist(file_ticker: str, by_norm: dict[str, list]):
    g = norm_symbol(file_ticker)
    cands = by_norm.get(g)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0][0]
    gt = file_ticker.upper().strip()
    for wl, asset in cands:
        if (asset.symbol or "").upper() == gt:
            return wl
    return cands[0][0]


def main():
    parser = argparse.ArgumentParser(
        description="Importar bloques === TICKER [MODO] === → watchlist FollowUp"
    )
    parser.add_argument("file", type=Path, help="Fichero .txt con bloques campo: valor")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = args.file.read_text(encoding="utf-8", errors="replace")
    blocks = parse_extract_file(text)
    if not blocks:
        print("No se encontraron bloques === TICKER [modo] ===", file=sys.stderr)
        sys.exit(1)

    from app import create_app, db
    from app.models.watchlist import WATCHLIST_MANUAL_FIELD_KEYS
    from app.services.watchlist_metrics_service import WatchlistMetricsService
    from app.services.watchlist_service import WatchlistService

    app = create_app()
    with app.app_context():
        config = WatchlistService.get_or_create_config(args.user_id)
        by_norm = build_watchlist_index(args.user_id)

        updated = 0
        skipped_tickers = []
        fields_applied = 0
        errors = []

        for fticker, raw_fields in sorted(blocks.items(), key=lambda x: x[0]):
            wl = resolve_watchlist(fticker, by_norm)
            if not wl:
                skipped_tickers.append(fticker)
                continue

            sources_update = {}
            for key, raw in raw_fields.items():
                if key not in WATCHLIST_MANUAL_FIELD_KEYS:
                    continue
                try:
                    val = coerce_value(key, raw)
                except (ValueError, TypeError) as e:
                    errors.append(f"{fticker}.{key}={raw!r} ({e})")
                    continue
                setattr(wl, key, val)
                sources_update[key] = "ai"
                fields_applied += 1

            if sources_update:
                wl.merge_manual_field_sources(sources_update)
                WatchlistMetricsService.update_all_metrics(wl, config=config, asset=wl.asset)
                updated += 1
                print(f"OK {fticker} → watchlist_id={wl.id} asset={wl.asset.symbol} fields={len(sources_update)}")
            else:
                print(f"— {fticker}: sin campos reconocidos")

        earnings_in_file = [t for t, flds in blocks.items() if "next_earnings_date" in flds]
        print(
            f"\nnext_earnings_date en el archivo: {len(earnings_in_file)} ticker(s): "
            + (", ".join(sorted(earnings_in_file, key=str.lower)) if earnings_in_file else "(ninguno)")
        )

        if args.dry_run:
            db.session.rollback()
            print("\n(dry-run: no se ha guardado nada)")
        else:
            db.session.commit()
            print(
                f"\nHecho: filas actualizadas={updated}, campos escritos={fields_applied}, errores parse={len(errors)}"
            )

        if skipped_tickers:
            print(f"\nTickers no encontrados en watchlist ({len(skipped_tickers)}):", ", ".join(skipped_tickers))
        if errors:
            print("\nValores omitidos:", *errors[:30], sep="\n")
            if len(errors) > 30:
                print(f"... y {len(errors) - 30} más")

    return 0


if __name__ == "__main__":
    sys.exit(main())
