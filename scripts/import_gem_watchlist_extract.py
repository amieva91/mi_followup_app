#!/usr/bin/env python3
"""
Importa bloques `=== TICKER [modo] ===` con líneas `campo: valor` (salida tipo Gem / Deep Research)
en los campos manuales de watchlist. Marca todo como origen `ai`.

Uso (desde la raíz del repo, con venv activo):
  python scripts/import_gem_watchlist_extract.py --user-id 3 /ruta/al/informe.txt
  python scripts/import_gem_watchlist_extract.py --user-id 3 --dry-run /ruta/al/informe.txt
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Raíz del proyecto
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BLOCK_RE = re.compile(r"^===\s+(\S+)\s+\[(\w+)\]\s*===\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^([a-z][a-z0-9_]*)\s*:\s*(.*)$", re.I)


def norm_symbol(sym: str) -> str:
    s = (sym or "").upper().strip()
    for suf in (".HK", ".L", "-HK"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def parse_gem_file(text: str) -> dict[str, dict[str, str]]:
    """Por ticker, último valor gana (bloques duplicados p. ej. SPR)."""
    matches = list(BLOCK_RE.finditer(text))
    out: dict[str, dict[str, str]] = {}
    for i, m in enumerate(matches):
        ticker = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]
        row = out.setdefault(ticker, {})
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            fm = FIELD_RE.match(line)
            if not fm:
                continue
            k = fm.group(1).lower()
            v = fm.group(2).strip()
            if v in ("", "—", "-"):
                continue
            row[k] = v
    return out


def coerce_value(key: str, raw: str):
    from app.models.watchlist import WATCHLIST_MANUAL_DATE_KEYS, WATCHLIST_MANUAL_STRING_KEYS

    raw = raw.strip()
    if key in WATCHLIST_MANUAL_DATE_KEYS:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    if key in WATCHLIST_MANUAL_STRING_KEYS:
        return str(raw)[:32]
    return float(raw.replace(",", ".").replace(" ", ""))


def build_watchlist_index(user_id: int) -> dict[str, tuple]:
    """
    norm(symbol) -> (Watchlist, Asset).
    Si hay colisión de norm, preferir coincidencia exacta de símbolo al resolver.
    """
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


def resolve_watchlist(gem_ticker: str, by_norm: dict[str, list]):
    g = norm_symbol(gem_ticker)
    cands = by_norm.get(g)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0][0]
    # Colisión: intentar símbolo exacto (mayús)
    gt = gem_ticker.upper().strip()
    for wl, asset in cands:
        if (asset.symbol or "").upper() == gt:
            return wl
    return cands[0][0]


def main():
    parser = argparse.ArgumentParser(description="Importar extracción Gem → watchlist")
    parser.add_argument("file", type=Path, help="Fichero de texto del Gem")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = args.file.read_text(encoding="utf-8", errors="replace")
    blocks = parse_gem_file(text)
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

        for gem_ticker, raw_fields in sorted(blocks.items(), key=lambda x: x[0]):
            wl = resolve_watchlist(gem_ticker, by_norm)
            if not wl:
                skipped_tickers.append(gem_ticker)
                continue

            sources_update = {}
            for key, raw in raw_fields.items():
                if key not in WATCHLIST_MANUAL_FIELD_KEYS:
                    continue
                try:
                    val = coerce_value(key, raw)
                except (ValueError, TypeError) as e:
                    errors.append(f"{gem_ticker}.{key}={raw!r} ({e})")
                    continue
                setattr(wl, key, val)
                sources_update[key] = "ai"
                fields_applied += 1

            if sources_update:
                wl.merge_manual_field_sources(sources_update)
                WatchlistMetricsService.update_all_metrics(wl, config=config, asset=wl.asset)
                updated += 1
                print(f"OK {gem_ticker} → watchlist_id={wl.id} asset={wl.asset.symbol} fields={len(sources_update)}")
            else:
                print(f"— {gem_ticker}: sin campos reconocidos")

        if args.dry_run:
            db.session.rollback()
            print("\n(dry-run: no se ha guardado nada)")
        else:
            db.session.commit()
            print(
                f"\nHecho: filas watchlist actualizadas={updated}, campos escritos={fields_applied}, errores parse={len(errors)}"
            )

        if skipped_tickers:
            print(f"\nTickers no encontrados en tu watchlist ({len(skipped_tickers)}):", ", ".join(skipped_tickers))
        if errors:
            print("\nValores omitidos:", *errors[:30], sep="\n")
            if len(errors) > 30:
                print(f"... y {len(errors) - 30} más")

    return 0


if __name__ == "__main__":
    sys.exit(main())
