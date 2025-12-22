# Resumen Final: Investigación del Cálculo de Apalancamiento

## Fecha: 19 Diciembre 2025

### 📊 Situación Actual

**Datos DeGiro:**
- Cuenta Completa: € 70,623.95
- Cartera: € 99,882.46
- EUR (apalancamiento): € -29,258.51
- Total B/P: € 47,170.31

**Datos App:**
- Valor Total Cartera: € 97,999.55
- Coste Total: € 83,040.82
- Dinero Usuario: € 34,286.03
- Apalancamiento: € 48,754.79
- P&L No Realizado: € 14,958.73

**Diferencia en Apalancamiento:**
- DeGiro: € 29,258.51
- App: € 48,754.79
- **Diferencia: € 19,496.28**

### 🔍 Hallazgos Clave

1. **Verificación de Fórmula DeGiro:**
   - Cuenta Completa = Cartera + EUR = Cartera - Apalancamiento ✓
   - 70,623.95 = 99,882.46 - 29,258.51 ✓

2. **Hipótesis sobre Base de Cálculo:**
   - **Si DeGiro usa COSTE:**
     - Necesitaría Dinero Usuario = 83,040.82 - 29,258.51 = **53,782.31**
     - Tenemos: 34,286.03
     - **Diferencia: 19,496.28** (exactamente la diferencia en apalancamiento)
   - **Si DeGiro usa VALOR DE MERCADO:**
     - Necesitaría Dinero Usuario = 97,999.55 - 29,258.51 = **68,741.04**
     - Tenemos: 34,286.03
     - Diferencia: 34,455.01

3. **Componentes del Dinero Usuario (App):**
   - Depósitos: € 36,718.98
   - Retiradas: € 33,499.00
   - P&L Realizado: € 31,395.21
   - Dividendos: € 12,478.32
   - Comisiones: € 12,807.48
   - **Total: € 34,286.03**

4. **Error de Visualización Encontrado:**
   - En `dashboard.html` línea 487 hay un signo negativo hardcodeado
   - `-{{ metrics.leverage.user_money|decimal_eu(2) }} EUR`
   - Esto hace que se muestre negativo aunque el valor es positivo

### 💡 Observaciones Importantes

1. **Si DeGiro usa COSTE (más probable):**
   - La diferencia en apalancamiento (19,496.28) es EXACTAMENTE igual a la diferencia necesaria en Dinero Usuario
   - Esto sugiere que DeGiro calcula el "Dinero Usuario" de forma diferente
   - Necesitaríamos añadir ~19,496€ al Dinero Usuario para igualar

2. **"Cuenta Completa" de DeGiro:**
   - No coincide exactamente con nuestro cálculo de "Dinero Usuario" + P&L No Realizado (49,244.76)
   - Diferencia: 70,623.95 - 49,244.76 = 21,379.19
   - Esto sugiere que "Cuenta Completa" podría representar algo diferente

3. **No se encontraron transacciones faltantes:**
   - Todos los tipos de transacciones están siendo contabilizados
   - No hay intereses en la BD
   - Las conversiones de moneda parecen correctas

### ❓ Preguntas Pendientes

1. **¿Qué está añadiendo DeGiro al "Dinero Usuario" que nosotros no?**
   - ¿Hay algún ajuste o componente que no estamos considerando?
   - ¿Calculan el P&L Realizado de forma diferente?
   - ¿Hay comisiones o fees que no estamos contabilizando correctamente?

2. **¿DeGiro realmente usa COSTE o VALOR DE MERCADO?**
   - La evidencia sugiere COSTE, pero la diferencia persiste
   - ¿Podría haber alguna fórmula intermedia?

3. **¿Qué representa exactamente "Cuenta Completa" en DeGiro?**
   - ¿Es realmente "Dinero Usuario" o es otra métrica?
   - ¿Cómo se relaciona con el cálculo del apalancamiento?

### 📝 Próximos Pasos Sugeridos

1. **Investigar la documentación de DeGiro** sobre cómo calculan estas métricas
2. **Comparar transacción por transacción** el P&L Realizado con los CSVs de DeGiro
3. **Verificar si hay comisiones o ajustes** que no estamos considerando
4. **Revisar si "Cuenta Completa"** tiene una definición específica diferente a "Dinero Usuario"
5. **Comparar con otras capturas** de DeGiro para verificar consistencia

### 🔧 Correcciones Necesarias (sin cambios en lógica)

1. **Corregir visualización del "Dinero Usuario"** en `dashboard.html` línea 487:
   - Quitar el signo negativo hardcodeado
   - Mostrar el valor positivo correctamente

