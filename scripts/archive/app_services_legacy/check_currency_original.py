#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.services.parsers.degiro_parser import DeGiroParser

p = DeGiroParser()
d = p.parse('uploads/Degiro.csv')
gqg = [x for x in d['dividends'] if 'GQG' in x.get('symbol', '')][0]
print('Keys:', gqg.keys())
print('currency_original:', gqg.get('currency_original'))

