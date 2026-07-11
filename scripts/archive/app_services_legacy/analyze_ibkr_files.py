"""
Analiza los 3 archivos de IBKR para ver todas las transacciones
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.csv_detector import detect_and_parse
from collections import defaultdict


def analyze_ibkr_file(filepath):
    """Analiza un archivo IBKR y retorna estadísticas"""
    print(f"\n{'='*80}")
    print(f"📄 Archivo: {filepath}")
    print(f"{'='*80}")
    
    if not os.path.exists(filepath):
        print(f"❌ Archivo no encontrado")
        return
    
    try:
        parsed = detect_and_parse(filepath)
        
        print(f"\n📊 Resumen:")
        print(f"   - Trades: {len(parsed['trades'])}")
        print(f"   - Holdings: {len(parsed['holdings'])}")
        print(f"   - Dividends: {len(parsed['dividends'])}")
        
        # Analizar transacciones por símbolo
        symbol_stats = defaultdict(lambda: {'BUY': 0, 'SELL': 0, 'BUY_qty': 0, 'SELL_qty': 0})
        
        for trade in parsed['trades']:
            symbol = trade['symbol']
            tx_type = trade['transaction_type']
            qty = trade['quantity']
            
            symbol_stats[symbol][tx_type] += 1
            symbol_stats[symbol][f'{tx_type}_qty'] += qty
        
        # Mostrar símbolos con transacciones
        print(f"\n📝 Transacciones por símbolo (ordenado por total):")
        sorted_symbols = sorted(symbol_stats.items(), 
                               key=lambda x: x[1]['BUY'] + x[1]['SELL'], 
                               reverse=True)
        
        for symbol, stats in sorted_symbols:
            total_buy = stats['BUY_qty']
            total_sell = stats['SELL_qty']
            balance = total_buy - total_sell
            
            print(f"\n   {symbol:30s}")
            print(f"      BUY:  {stats['BUY']:2d} transacciones | {total_buy:8.0f} unidades")
            print(f"      SELL: {stats['SELL']:2d} transacciones | {total_sell:8.0f} unidades")
            print(f"      BALANCE: {balance:8.0f} unidades")
            
            if balance <= 0:
                print(f"      ⚠️  Posición CERRADA (vendida completamente)")
        
        # Buscar específicamente IGC
        print(f"\n🔍 Búsqueda específica de 'IGC':")
        igc_found = False
        for symbol, stats in symbol_stats.items():
            if 'IGC' in symbol.upper():
                igc_found = True
                print(f"   ✅ Encontrado: {symbol}")
                print(f"      BUY:  {stats['BUY']} transacciones | {stats['BUY_qty']:.0f} unidades")
                print(f"      SELL: {stats['SELL']} transacciones | {stats['SELL_qty']:.0f} unidades")
                print(f"      BALANCE: {stats['BUY_qty'] - stats['SELL_qty']:.0f} unidades")
                
                # Mostrar detalles de las transacciones de IGC
                print(f"\n      📋 Detalle de transacciones:")
                for trade in parsed['trades']:
                    if 'IGC' in trade['symbol'].upper():
                        print(f"         {trade['date_time']} | {trade['transaction_type']:4s} | {trade['quantity']:8.0f} @ {trade['price']:.2f} {trade['currency']}")
        
        if not igc_found:
            print(f"   ❌ No se encontró 'IGC' en este archivo")
        
    except Exception as e:
        print(f"❌ Error al parsear: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Analiza los 3 archivos de IBKR"""
    print("=" * 80)
    print("ANÁLISIS DE ARCHIVOS IBKR")
    print("=" * 80)
    
    files = [
        'uploads/U12722327_20230912_20240911.csv',  # IBKR 2023-2024
        'uploads/U12722327_20240912_20250911.csv',  # IBKR 2024-2025
        'uploads/U12722327_20250912_20251006.csv',  # IBKR 2025 (actual)
    ]
    
    for filepath in files:
        analyze_ibkr_file(filepath)
    
    print(f"\n{'='*80}")
    print("✅ Análisis completado")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()

