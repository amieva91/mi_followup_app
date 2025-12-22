# Resumen de Investigación: Cálculo de Apalancamiento DeGiro

## Fecha: 19 Diciembre 2025

### 📊 Datos de DeGiro

- **Cuenta Completa**: € 69,519.94
- **Cartera**: € 93,748.23
- **EUR** (saldo cash negativo = apalancamiento): € -24,228.29
- **Margen libre**: € 17,065.21
- **Total B/P**: € 46,066.31

### 💻 Datos de nuestra Aplicación

- **Valor Total Cartera**: € 94,332.19 (sin ajuste) / € 89,132.19 (ajustado por Abengoa)
- **Coste Total**: € 79,795.20
- **Dinero Usuario**: € 31,040.41
- **Dinero Prestado** (apalancamiento): € 48,754.79
- **P&L No Realizado**: € 14,536.99
- **P&L Total**: € 42,357.42

### ⚠️ Ajuste por Abengoa

- **Valor de Abengoa**: € 5,200.00 (quebrada, debe restarse de la cartera)
- **Cartera ajustada (App)**: € 89,132.19
- **Cartera ajustada (DeGiro, si cuenta Abengoa)**: € 88,548.23
- **Diferencia entre carteras ajustadas**: € 583.96 ✓ (muy cercano)

### 🔍 Fórmulas Verificadas de DeGiro

✓ **Cuenta Completa = Cartera + EUR = Cartera - Apalancamiento**
  - 69,519.94 = 93,748.23 + (-24,228.29) ✓

✓ **EUR = Cuenta Completa - Cartera**
  - -24,228.29 = 69,519.94 - 93,748.23 ✓

### 📐 Hipótesis Evaluadas

#### HIPÓTESIS A: DeGiro usa VALOR DE MERCADO (sin ajuste Abengoa)
- Si: Apalancamiento = Valor Cartera - Dinero Usuario
- Resultado: 93,748.23 - 31,040.41 = 62,707.82
- DeGiro muestra: 24,228.29
- **Diferencia: 38,479.53** ❌ No explica

#### HIPÓTESIS B: DeGiro usa VALOR DE MERCADO (con ajuste Abengoa)
- Si: Apalancamiento = Cartera (ajustada) - Dinero Usuario
- Resultado: 89,132.19 - 31,040.41 = 58,091.78
- DeGiro muestra: 24,228.29
- **Diferencia: 33,863.49** ❌ No explica

#### HIPÓTESIS C: DeGiro usa COSTE
- Si: Apalancamiento = Coste Total - Dinero Usuario
- Resultado: 79,795.20 - 31,040.41 = 48,754.79
- DeGiro muestra: 24,228.29
- **Diferencia: 24,526.50** ❌ No explica

#### HIPÓTESIS D: DeGiro calcula "Dinero Usuario" diferente
- Si: Dinero Usuario = Cartera - Apalancamiento
- Resultado: 93,748.23 - 24,228.29 = 69,519.94
- **Esto coincide EXACTAMENTE con "Cuenta Completa"** ✓
- Nuestro Dinero Usuario: 31,040.41
- **Diferencia: 38,479.53**

### 🔍 Observación Importante (HIPÓTESIS B con ajuste)

Si DeGiro cuenta Abengoa en su cartera y ajustamos:
- Cartera DeGiro ajustada: 88,548.23
- Dinero Usuario (Cuenta Completa): 69,519.94
- Apalancamiento resultante: 88,548.23 - 69,519.94 = 19,028.29
- DeGiro muestra: 24,228.29
- **Diferencia: -5,200.00** (exactamente Abengoa)

Esto sugiere que:
- DeGiro SÍ cuenta Abengoa en su cartera
- Pero el apalancamiento NO se calcula simplemente como "Cartera - Dinero Usuario"
- Hay algo más en el cálculo

### 📊 Análisis del Total B/P

- **DeGiro Total B/P**: € 46,066.31
- **Nuestro P&L Total**: € 42,357.42
- **Diferencia**: -€ 3,708.89

**Componentes de nuestro P&L Total:**
- P&L Realizado: € 28,149.59
- P&L No Realizado: € 14,536.99
- Dividendos: € 12,478.32
- Comisiones: € 12,807.48
- **Total = Realizado + No Realizado + Dividendos - Comisiones**

**Intereses**: 0 transacciones en BD

### ❓ Preguntas Pendientes

1. **¿Cómo calcula DeGiro exactamente el apalancamiento?**
   - No parece ser simplemente "Cartera - Dinero Usuario"
   - No parece usar el coste histórico
   - Hay una diferencia sistemática de ~24,500€

2. **¿Qué incluye DeGiro en "Dinero Usuario"?**
   - "Cuenta Completa" = 69,519.94
   - Nuestro "Dinero Usuario" = 31,040.41
   - Diferencia: 38,479.53
   - ¿Hay componentes que no estamos considerando?

3. **¿El Total B/P de DeGiro incluye algo más?**
   - Diferencia de 3,708.89
   - No parece ser intereses (no hay en BD)
   - ¿Calculan las comisiones de forma diferente?

4. **¿Qué representa exactamente "Cuenta Completa"?**
   - Coincide con "Cartera - Apalancamiento"
   - Pero no coincide con nuestro "Dinero Usuario" calculado
   - ¿Es realmente el "Dinero Usuario" de DeGiro?

### 📝 Estado Actual

**NO hemos encontrado la fórmula exacta que usa DeGiro para calcular el apalancamiento.**

Las hipótesis evaluadas no explican completamente la diferencia de ~24,500€ (o ~19,000€ con ajuste de Abengoa).

**Próximos pasos sugeridos:**
1. Revisar documentación oficial de DeGiro sobre cómo calculan el apalancamiento
2. Verificar si hay transacciones o ajustes que no estamos contabilizando
3. Investigar si "Cuenta Completa" realmente representa "Dinero Usuario" o es otra métrica
4. Comparar con otras capturas de DeGiro para verificar consistencia

