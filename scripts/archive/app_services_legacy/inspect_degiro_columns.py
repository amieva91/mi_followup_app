"""
Script para inspeccionar las columnas del CSV TransaccionesDegiro
Específicamente las columnas 4 y 5 (centro de negociación y tipo de bolsa)
"""
import csv
import os

csv_path = "uploads/TransaccionesDegiro.csv"

if not os.path.exists(csv_path):
    print(f"❌ Archivo no encontrado: {csv_path}")
    print("Por favor, asegúrate de que el archivo esté en la carpeta uploads/")
    exit(1)

print("\n" + "="*80)
print("INSPECCIONANDO CSV TRANSACCIONES DEGIRO")
print("="*80)
print(f"Archivo: {csv_path}\n")

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    
    # Leer header
    header = next(reader)
    print("📋 HEADER (primeras 10 columnas):")
    for i, col in enumerate(header[:10]):
        print(f"   Columna {i}: '{col}'")
    
    print(f"\n📋 COLUMNAS ESPECÍFICAS:")
    if len(header) > 4:
        print(f"   Columna 4: '{header[4]}'")
    if len(header) > 5:
        print(f"   Columna 5: '{header[5]}'")
    
    print("\n" + "="*80)
    print("EJEMPLOS DE DATOS (primeras 10 transacciones)")
    print("="*80)
    
    for i, row in enumerate(reader):
        if i >= 10:  # Solo primeras 10
            break
        
        if len(row) > 5:
            print(f"\nTransacción {i+1}:")
            print(f"   Col 0 (Fecha): {row[0]}")
            print(f"   Col 1 (Hora): {row[1]}")
            print(f"   Col 2 (Producto): {row[2]}")
            print(f"   Col 3 (ISIN): {row[3]}")
            print(f"   Col 4: '{row[4]}'")  # ✅ Centro de negociación?
            print(f"   Col 5: '{row[5]}'")  # ✅ Tipo de bolsa?
            print(f"   Col 6 (Cantidad): {row[6]}")
            if len(row) > 8:
                print(f"   Col 8 (Moneda): {row[8]}")

print("\n" + "="*80)
print("ANÁLISIS DE COLUMNAS 4 Y 5")
print("="*80)

# Re-leer para analizar valores únicos
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    col4_values = set()
    col5_values = set()
    
    examples_by_col4 = {}
    
    for row in reader:
        if len(row) > 5:
            col4 = row[4].strip()
            col5 = row[5].strip()
            
            if col4:
                col4_values.add(col4)
                if col4 not in examples_by_col4:
                    examples_by_col4[col4] = {
                        'producto': row[2],
                        'isin': row[3],
                        'col5': col5,
                        'moneda': row[8] if len(row) > 8 else 'N/A'
                    }
            
            if col5:
                col5_values.add(col5)

print(f"\n📊 Valores únicos en Columna 4 ({len(col4_values)} valores):")
for val in sorted(col4_values):
    if val in examples_by_col4:
        ex = examples_by_col4[val]
        print(f"   '{val}' -> {ex['producto']} ({ex['isin']}, {ex['moneda']})")

print(f"\n📊 Valores únicos en Columna 5 ({len(col5_values)} valores):")
for val in sorted(col5_values):
    print(f"   '{val}'")

print("\n" + "="*80)
print("CONCLUSIONES")
print("="*80)
print("""
💡 Si la columna 4 contiene códigos MIC (Market Identifier Code):
   - Podríamos usarlo directamente con OpenFIGI
   - No necesitaríamos adivinar el exchange

💡 Si la columna 5 contiene tipo de bolsa:
   - Podría ayudar a filtrar resultados
   - Ejemplo: "XETRA", "NYSE", "LSE", etc.

🎯 SIGUIENTE PASO:
   - Verificar si los códigos de columna 4 son MIC codes válidos
   - Usar estos datos en el request a OpenFIGI
""")
print()

