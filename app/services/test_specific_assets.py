#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.parsers.degiro_parser import DeGiroParser

p = DeGiroParser()
d = p.parse('uploads/Degiro.csv')

print("\nBuscando CONSUN:")
consun = [x for x in d['dividends'] if 'CONSUN' in x['symbol'].upper()]
if consun:
    print(f"  ✅ {consun[0]['date']}: {consun[0]['amount']:.2f} {consun[0]['currency']}")
else:
    print("  ❌ NO ENCONTRADO")

print("\nBuscando GRIFOLS:")
grifols = [x for x in d['dividends'] if 'GRIFOLS' in x['symbol'].upper()]
if grifols:
    print(f"  ✅ {grifols[0]['date']}: {grifols[0]['amount']:.2f} {grifols[0]['currency']}")
else:
    print("  ❌ NO ENCONTRADO")

print("\nBuscando ALIBABA:")
alibaba = [x for x in d['dividends'] if 'ALIBABA' in x['symbol'].upper()]
if alibaba:
    for a in alibaba:
        print(f"  ✅ {a['date']}: {a['amount']:.2f} {a['currency']}")
else:
    print("  ❌ NO ENCONTRADO")

