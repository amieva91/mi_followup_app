"""
Script de test para probar los parsers de CSV
"""
import sys
import os
import json
from pprint import pprint

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.csv_detector import CSVDetector, detect_and_parse


def test_detector():
    """Prueba el detector con todos los CSVs"""
    print("=" * 80)
    print("TEST 1: Detector de formato")
    print("=" * 80)
    
    csv_files = [
        'uploads/IBKR.csv',
        'uploads/IBKR1.csv',
        'uploads/IBKR2.csv',
        'uploads/Degiro.csv'
    ]
    
    for file_path in csv_files:
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            continue
        
        format_type = CSVDetector.detect_format_from_file(file_path)
        print(f"✅ {file_path:30} → {format_type}")
    
    print()


def test_ibkr_parser():
    """Prueba el parser de IBKR con archivos reales"""
    print("=" * 80)
    print("TEST 2: IBKR Parser")
    print("=" * 80)
    
    csv_files = [
        'uploads/IBKR.csv',
        'uploads/IBKR1.csv',
        'uploads/IBKR2.csv'
    ]
    
    for file_path in csv_files:
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            continue
        
        print(f"\n📄 Parseando: {file_path}")
        print("-" * 80)
        
        try:
            # Usar el detector automático
            data = detect_and_parse(file_path)
            
            # Mostrar resumen
            print(f"\n🏦 Broker: {data['broker']}")
            
            # Account info
            if data['account_info']:
                print(f"\n👤 Información de cuenta:")
                for key, value in data['account_info'].items():
                    print(f"  • {key}: {value}")
            
            # Trades
            if data['trades']:
                print(f"\n💱 Trades encontrados: {len(data['trades'])}")
                print(f"  Mostrando primeros 3:")
                for i, trade in enumerate(data['trades'][:3], 1):
                    print(f"    {i}. {trade['transaction_type']} {trade['quantity']} {trade['symbol']} @ {trade['price']} {trade['currency']}")
            
            # Holdings
            if data['holdings']:
                print(f"\n📊 Holdings encontrados: {len(data['holdings'])}")
                print(f"  Mostrando primeros 3:")
                for i, holding in enumerate(data['holdings'][:3], 1):
                    print(f"    {i}. {holding['symbol']}: {holding['quantity']} @ {holding['current_price']} {holding['currency']} (P&L: {holding['unrealized_pl']})")
            
            # Dividends
            if data['dividends']:
                print(f"\n💰 Dividendos encontrados: {len(data['dividends'])}")
                print(f"  Mostrando primeros 3:")
                for i, div in enumerate(data['dividends'][:3], 1):
                    print(f"    {i}. {div['symbol']} ({div['date']}): {div['amount']} {div['currency']}")
            
            print()
            
        except Exception as e:
            print(f"❌ Error parseando {file_path}: {e}")
            import traceback
            traceback.print_exc()


def test_full_export():
    """Exporta todos los datos parseados a JSON para inspección"""
    print("=" * 80)
    print("TEST 3: Exportar datos parseados a JSON")
    print("=" * 80)
    
    file_path = 'uploads/IBKR.csv'
    
    if not os.path.exists(file_path):
        print(f"❌ Archivo no encontrado: {file_path}")
        return
    
    try:
        data = detect_and_parse(file_path)
        
        # Guardar a JSON
        output_file = 'uploads/IBKR_parsed.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Datos exportados a: {output_file}")
        print(f"   - Trades: {len(data['trades'])}")
        print(f"   - Holdings: {len(data['holdings'])}")
        print(f"   - Dividends: {len(data['dividends'])}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("\n🧪 PRUEBAS DE PARSERS CSV\n")
    
    test_detector()
    test_ibkr_parser()
    test_full_export()
    
    print("\n✅ Tests completados\n")

