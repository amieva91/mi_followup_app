# 🔄 Formateo de Producción - Partir de Cero

## Respuesta a tus preguntas

### 1. ¿La solución faltaba solo en producción o en ambos?
**Respuesta: Faltaba en AMBOS entornos**

El código original siempre pasaba `use_current_prices=True` para el valor final (VF), incluso para años pasados. Esto causaba que se intentaran usar precios actuales de mercado para calcular valores históricos.

**Por qué funcionaba mejor en desarrollo:**
- Probablemente tenía menos transacciones
- O los datos eran diferentes (menos complejos)
- El bug se manifestaba menos visiblemente

### 2. ¿Se puede formatear producción?

**SÍ**, he creado el script `format_production.py` para esto.

## Instrucciones para Formatear Producción

### Opción 1: Ejecutar desde tu máquina (recomendado)

```bash
# 1. Copiar el script a producción
scp -i ~/.ssh/ssh-key-2025-08-21.key format_production.py ubuntu@140.238.120.92:/home/ubuntu/www/

# 2. Conectar a producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92

# 3. En producción, ejecutar el script
cd /home/ubuntu/www
chmod +x format_production.py
source venv/bin/activate
python format_production.py

# 4. Cuando pida confirmación, escribir "SI" (en mayúsculas)

# 5. Reiniciar la aplicación
sudo systemctl restart followup.service
```

### Opción 2: Ejecutar directamente en producción

```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92 'cd /home/ubuntu/www && source venv/bin/activate && python format_production.py'
```

## ⚠️ ADVERTENCIAS

1. **Esta operación es IRREVERSIBLE**
2. Se eliminarán:
   - Todos los assets y holdings
   - Todas las transacciones
   - Todas las cuentas de broker
   - Todas las métricas
3. Se mantendrán:
   - Usuarios
   - Categorías de gastos/ingresos
   - AssetRegistry global (cache compartida)
   - Configuración de brokers

## Después del Formateo

1. Crear nuevas cuentas de broker (IBKR, DeGiro)
2. Importar CSVs desde cero
3. Verificar que las rentabilidades año a año sean correctas

## Verificación

Después de importar, puedes usar el script de diagnóstico:

```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92 'cd /home/ubuntu/www && source venv/bin/activate && python diagnose_yearly_returns.py production 1'
```
