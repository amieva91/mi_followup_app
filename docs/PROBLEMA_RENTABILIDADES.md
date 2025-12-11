# 🔍 Problema: Discrepancias en Rentabilidades Año a Año entre Desarrollo y Producción

## Problema Identificado

Las rentabilidades año a año muestran discrepancias significativas entre desarrollo y producción, a pesar de usar los mismos CSVs.

### Ejemplos de Discrepancias

**2024:**
- Desarrollo: VI=38,548.09, VF=64,839.15, Return=29.51%
- Producción: VI=390,864.17, VF=66,345.56, Return=-83.81%
- **Diferencia**: VI es 10x mayor en producción

**2023:**
- Desarrollo: VI=53,845.90, VF=38,548.09, Return=-28.51%
- Producción: VI=53,845.90, VF=390,864.17, Return=634.23%
- **Diferencia**: VF es 10x mayor en producción

### Diferencias en Transacciones
- WITHDRAWAL: Dev=78, Prod=79 (+1)
- DIVIDEND: Dev=174, Prod=179 (+5)
- FEE: Dev=188, Prod=191 (+3)

## Causa Raíz

1. **Uso incorrecto de precios actuales en fechas históricas:**
   - En `modified_dietz.py`, siempre se pasaba `use_current_prices=True` para el valor final (VF)
   - Esto causaba que para años pasados (ej: 2024-12-31) se intentara usar precios actuales
   - Aunque la lógica en `portfolio_valuation.py` debería prevenir esto, había un bug

2. **Datos diferentes entre entornos:**
   - Hay más transacciones en producción (probablemente de imports adicionales)
   - Esto causa que los cálculos sean diferentes

## Solución Implementada

### Cambio en `modified_dietz.py`:

```python
# ANTES (INCORRECTO):
VF = PortfolioValuation.get_value_at_date(
    user_id, 
    end_date, 
    use_current_prices=True  # ❌ Siempre True, incluso para años pasados
)

# DESPUÉS (CORRECTO):
# Determinar automáticamente si usar precios actuales
today = datetime.now().date()
is_end_date_today = (end_date.date() >= today)
VF = PortfolioValuation.get_value_at_date(
    user_id, 
    end_date, 
    use_current_prices=is_end_date_today  # ✅ Solo True si es HOY
)
```

### Cambio en `get_yearly_returns()`:

Ahora se pasa explícitamente `use_current_prices_end=is_ytd` para que solo el año actual (YTD) use precios actuales.

## Verificación

Después del fix:
- Los años pasados usarán precios de compra (average_buy_price) para el VF
- Solo el año actual (YTD) usará precios actuales de mercado
- Esto debería hacer que los cálculos sean consistentes entre entornos

## Próximos Pasos

1. ✅ Fix aplicado en código
2. ⏳ Probar en desarrollo
3. ⏳ Desplegar a producción
4. ⏳ Verificar que los datos coincidan

## Nota Importante

Las diferencias en número de transacciones (WITHDRAWAL, DIVIDEND, FEE) sugieren que hay datos diferentes entre los dos entornos. Esto puede deberse a:
- Imports adicionales en producción
- Transacciones manuales diferentes
- Necesita investigación adicional

