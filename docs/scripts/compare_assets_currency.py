#!/usr/bin/env python3
"""
Compara dos JSON exportados por export_assets_currency.py (local vs producción).
Lista símbolos que tienen distinta currency entre entornos o donde asset.currency
no coincide con la moneda de las transacciones.

Uso:
  python docs/scripts/compare_assets_currency.py local_assets.json prod_assets.json

Si solo pasas un archivo, muestra advertencias de currency_mismatch en ese entorno.
"""
import sys
import json
from pathlib import Path


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print('Uso: python compare_assets_currency.py <local_assets.json> [prod_assets.json]')
        sys.exit(1)
    path_a = Path(sys.argv[1])
    path_b = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if not path_a.exists():
        print(f'No existe: {path_a}')
        sys.exit(1)
    data_a = load_json(path_a)
    name_a = path_a.stem
    assets_a = {a['symbol']: a for a in data_a.get('assets', []) if a.get('symbol')}
    if path_b is None:
        print(f'=== Solo un archivo: {path_a} ===')
        print('Símbolos con currency distinta a la de sus transacciones (currency_mismatch):')
        mismatches = [a for a in data_a.get('assets', []) if a.get('currency_mismatch')]
        if not mismatches:
            print('  (ninguno)')
        for a in mismatches:
            print(f"  {a['symbol']}  asset_id={a['asset_id']}  currency={a['currency']}  txns_currencies={a.get('currencies_in_transactions', [])}")
        return
    if not path_b.exists():
        print(f'No existe: {path_b}')
        sys.exit(1)
    data_b = load_json(path_b)
    name_b = path_b.stem
    assets_b = {a['symbol']: a for a in data_b.get('assets', []) if a.get('symbol')}

    all_symbols = sorted(set(assets_a.keys()) | set(assets_b.keys()))
    different_currency = []
    only_in_a = []
    only_in_b = []
    for sym in all_symbols:
        va = assets_a.get(sym)
        vb = assets_b.get(sym)
        if va is None:
            only_in_b.append((sym, vb))
            continue
        if vb is None:
            only_in_a.append((sym, va))
            continue
        if (va.get('currency') or 'EUR') != (vb.get('currency') or 'EUR'):
            different_currency.append({
                'symbol': sym,
                'currency_a': va.get('currency'),
                'currency_b': vb.get('currency'),
                'asset_id_a': va.get('asset_id'),
                'asset_id_b': vb.get('asset_id'),
            })

    print('=== Símbolos con distinta currency entre entornos ===')
    print(f'  {name_a} vs {name_b}\n')
    if different_currency:
        for d in different_currency:
            print(f"  {d['symbol']}:  {name_a}=({d['currency_a']}, asset_id={d['asset_id_a']})  "
                  f"{name_b}=({d['currency_b']}, asset_id={d['asset_id_b']})")
        print(f'\nTotal: {len(different_currency)} símbolo(s). Corrige Asset.currency en el entorno incorrecto y vuelve a Recalcular.')
    else:
        print('  (ninguno)')
    if only_in_a:
        print(f'\nSolo en {name_a}: {", ".join(s for s, _ in only_in_a)}')
    if only_in_b:
        print(f'\nSolo en {name_b}: {", ".join(s for s, _ in only_in_b)}')

    print('\n=== Currency distinta a la de las transacciones (en cada archivo) ===')
    for label, data in [(name_a, data_a), (name_b, data_b)]:
        mismatches = [a for a in data.get('assets', []) if a.get('currency_mismatch')]
        print(f'  {label}: {len(mismatches)}')
        for a in mismatches[:20]:
            print(f"    {a['symbol']}  currency={a['currency']}  txns_currencies={a.get('currencies_in_transactions', [])}")
        if len(mismatches) > 20:
            print(f'    ... y {len(mismatches) - 20} más')


if __name__ == '__main__':
    main()
