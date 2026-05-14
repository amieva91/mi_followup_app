#!/usr/bin/env python3
"""
Verificación previa: Yahoo Finance Chart API v8 para tickers del motor de estrategia global.

No escribe en BD. Comprueba:
  1) Chart sin parámetros (cotización ligera, equivalente a la ruta de PriceUpdater.fetch_yahoo_chart_quote).
  2) Chart con range=… & interval=1d — suficientes cierres para MA200.

Solo urllib + json (sin dependencias extra). Uso:

  python3 scripts/verify_yahoo_global_strategy_tickers.py

Opcional (misma función que en app, requiere venv con Flask/requests):
  ./venv/bin/python scripts/verify_yahoo_global_strategy_tickers.py --also-price-updater

Código de salida: 0 si todos los checks obligatorios pasan, 1 si no.

Por defecto solo se validan **^TNX, ^IRX, 3188.HK** (yield US + Asia), que sí devuelven
historial diario para MA200. El bloque EU (VSTOXX) requiere decisión de producto: usar
`--include-eu-vstoxx` para incluir `V2TX.DE` en los checks estrictos (hoy suele **fallar**
el requisito de >=200 cierres vía Chart v8).
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TICKERS = ("^TNX", "^IRX", "3188.HK")
EU_VSTOXX_TICKER = "V2TX.DE"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com/",
}


def _chart_url(ticker: str, params: Optional[Dict[str, str]] = None) -> str:
    path_ticker = urllib.parse.quote(str(ticker).strip(), safe="")
    base = f"https://query1.finance.yahoo.com/v8/finance/chart/{path_ticker}"
    if not params:
        return base
    q = urllib.parse.urlencode(params)
    return f"{base}?{q}"


def fetch_chart(
    ticker: str,
    *,
    range_: Optional[str] = None,
    interval: Optional[str] = None,
    timeout: float = 15.0,
) -> Tuple[Optional[dict], Optional[str]]:
    params = {}
    if range_:
        params["range"] = range_
    if interval:
        params["interval"] = interval
    url = _chart_url(ticker, params or None)
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"URL error: {e}"
    except json.JSONDecodeError as e:
        return None, f"JSON: {e}"

    err = (data.get("chart") or {}).get("error")
    if err:
        desc = err.get("description") if isinstance(err, dict) else str(err)
        return None, f"chart.error: {desc}"
    res = (data.get("chart") or {}).get("result") or []
    if not res:
        return None, "chart.result vacío"
    return data, None


def _meta_prices(chart_json: dict) -> Tuple[Optional[float], Optional[float]]:
    res = chart_json["chart"]["result"][0]
    meta = res.get("meta") or {}
    def gf(k: str) -> Optional[float]:
        v = meta.get(k)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    price = gf("regularMarketPrice")
    prev = gf("chartPreviousClose") or gf("previousClose")
    return price, prev


def _non_null_closes(chart_json: dict) -> List[float]:
    res = chart_json["chart"]["result"][0]
    quotes = (res.get("indicators") or {}).get("quote") or [{}]
    closes = (quotes[0] or {}).get("close") or []
    out: List[float] = []
    for v in closes:
        if v is not None and isinstance(v, (int, float)) and float(v) > 0:
            out.append(float(v))
    return out


def check_light(ticker: str, timeout: float) -> Dict[str, Any]:
    """Sin range/interval: debe traer meta.regularMarketPrice (misma idea que fetch_yahoo_chart_quote)."""
    data, err = fetch_chart(ticker, range_=None, interval=None, timeout=timeout)
    if err:
        return {"ticker": ticker, "ok": False, "phase": "light", "error": err}
    price, prev = _meta_prices(data)
    ok = price is not None and price > 0
    return {
        "ticker": ticker,
        "ok": ok,
        "phase": "light",
        "regular_market_price": price,
        "previous_close": prev,
        "error": None if ok else "meta sin regularMarketPrice válido",
    }


def check_history(
    ticker: str, *, min_closes: int, range_: str, interval: str, timeout: float
) -> Dict[str, Any]:
    data, err = fetch_chart(ticker, range_=range_, interval=interval, timeout=timeout)
    if err:
        return {"ticker": ticker, "ok": False, "phase": "history", "error": err, "close_count": 0}
    closes = _non_null_closes(data)
    ok = len(closes) >= min_closes
    return {
        "ticker": ticker,
        "ok": ok,
        "phase": "history",
        "close_count": len(closes),
        "last_close": closes[-1] if closes else None,
        "range": range_,
        "interval": interval,
        "error": None if ok else f"menos de {min_closes} cierres no nulos ({len(closes)})",
    }


def run_price_updater_checks(tickers: List[str], timeout: float) -> List[Dict[str, Any]]:
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    from app import create_app
    from app.services.market_data.services.price_updater import PriceUpdater

    out: List[Dict[str, Any]] = []
    app = create_app()
    with app.app_context():
        for t in tickers:
            q = PriceUpdater.fetch_yahoo_chart_quote(t)
            ok = bool(q and q.get("regular_market_price") is not None)
            out.append({"ticker": t, "ok": ok, "phase": "price_updater", "quote": q})
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--tickers",
        default=",".join(DEFAULT_TICKERS),
        help=f"CSV (por defecto: {','.join(DEFAULT_TICKERS)}). ^V2TX→404; V2TX.DE vía --include-eu-vstoxx.",
    )
    p.add_argument(
        "--include-eu-vstoxx",
        action="store_true",
        help=f"Incluye {EU_VSTOXX_TICKER} en checks estrictos (MA200; suele fallar en Yahoo chart).",
    )
    p.add_argument(
        "--no-eu-probe-footer",
        action="store_true",
        help="No imprimir el diagnóstico informativo de VSTOXX al final si el gate principal pasa.",
    )
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--min-closes", type=int, default=200)
    p.add_argument("--range", dest="range_", default="2y")
    p.add_argument("--interval", default="1d")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--also-price-updater",
        action="store_true",
        help="Además ejecuta PriceUpdater.fetch_yahoo_chart_quote (requiere venv Flask).",
    )
    args = p.parse_args()
    tickers = [x.strip() for x in args.tickers.split(",") if x.strip()]
    if args.include_eu_vstoxx and EU_VSTOXX_TICKER not in tickers:
        tickers.append(EU_VSTOXX_TICKER)

    light = [check_light(t, args.timeout) for t in tickers]
    hist = [
        check_history(
            t,
            min_closes=args.min_closes,
            range_=args.range_,
            interval=args.interval,
            timeout=args.timeout,
        )
        for t in tickers
    ]

    pu: List[Dict[str, Any]] = []
    if args.also_price_updater:
        try:
            pu = run_price_updater_checks(tickers, args.timeout)
        except Exception as e:
            pu = [{"ticker": "ALL", "ok": False, "phase": "price_updater", "error": str(e)}]

    all_ok = all(r["ok"] for r in light) and all(r["ok"] for r in hist)
    if args.also_price_updater and pu:
        all_ok = all_ok and all(r.get("ok") for r in pu)

    payload = {"urllib_light": light, "urllib_history": hist}
    if pu:
        payload["price_updater"] = pu

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print("=== Chart API (urllib, sin range = cotización ligera) ===")
        for r in light:
            print(f"  [{'OK' if r['ok'] else 'FAIL'}] {r['ticker']}: price={r.get('regular_market_price')} prev={r.get('previous_close')} {r.get('error') or ''}")
        print(f"\n=== Chart API (urllib, range={args.range_} interval={args.interval}, >= {args.min_closes} cierres) ===")
        for r in hist:
            print(
                f"  [{'OK' if r['ok'] else 'FAIL'}] {r['ticker']}: closes={r['close_count']} last={r.get('last_close')} {r.get('error') or ''}"
            )
        if pu:
            print("\n=== PriceUpdater.fetch_yahoo_chart_quote (app) ===")
            for r in pu:
                print(f"  [{'OK' if r.get('ok') else 'FAIL'}] {r.get('ticker')}: {r.get('quote')} {r.get('error') or ''}")

    if not all_ok:
        print("\nResultado: NO SATISFACTORIO — no continuar integración en programa hasta resolver.")
        return 1
    print("\nResultado: SATISFACTORIO — Yahoo devuelve datos coherentes para estos tickers.")
    if not args.no_eu_probe_footer and EU_VSTOXX_TICKER not in tickers:
        print(f"\n--- Diagnóstico informativo {EU_VSTOXX_TICKER} (no afecta al exit code) ---")
        l = check_light(EU_VSTOXX_TICKER, args.timeout)
        h = check_history(
            EU_VSTOXX_TICKER,
            min_closes=args.min_closes,
            range_=args.range_,
            interval=args.interval,
            timeout=args.timeout,
        )
        print(f"  light: {'OK' if l['ok'] else 'FAIL'} {l}")
        print(f"  history: {'OK' if h['ok'] else 'FAIL'} closes={h['close_count']} {h.get('error') or ''}")
        if not h["ok"]:
            print(
                "  Nota: Chart v8 no ofrece aquí serie diaria usable para MA200; "
                "definir otra fuente o ticker antes del bloque EU en producción.",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
