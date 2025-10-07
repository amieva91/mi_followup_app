"""
Verifica si IGC e IGCl tienen el mismo ISIN
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.csv_detector import detect_and_parse

# Archivo 1
parsed1 = detect_and_parse('uploads/U12722327_20230912_20240911.csv')
igc_trades1 = [t for t in parsed1['trades'] if 'IGC' in t['symbol'].upper()]
print('Archivo 1 - IGC (compra):')
for t in igc_trades1:
    print(f'  Símbolo: {t["symbol"]:10s} | ISIN: {t.get("isin", "NO ISIN")} | {t["transaction_type"]} {t["quantity"]} @ {t["price"]}')

# Archivo 3
parsed3 = detect_and_parse('uploads/U12722327_20250912_20251006.csv')
igc_trades3 = [t for t in parsed3['trades'] if 'IGC' in t['symbol'].upper()]
print('\nArchivo 3 - IGCl (venta):')
for t in igc_trades3:
    print(f'  Símbolo: {t["symbol"]:10s} | ISIN: {t.get("isin", "NO ISIN")} | {t["transaction_type"]} {t["quantity"]} @ {t["price"]}')

