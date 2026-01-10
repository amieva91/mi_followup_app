# 🎨 Guía de Prueba de Colores - Watchlist

Esta guía te ayudará a probar todos los casos de colores en la watchlist.

## 📋 Columnas con Colores Configurables

### 1. **Fecha próximos resultados** (Manual)
- **Verde**: Fecha futura (days_diff > 0)
- **Amarillo**: Pasada ≤ X días (configurable, default 15 días)
- **Rojo**: Pasada > X días

**Cómo probar:**
1. Ve a un asset y edita "Fecha próximos resultados"
2. **Verde**: Pon una fecha futura (ej: `2025-12-31`)
3. **Amarillo**: Pon una fecha que haya pasado hace ≤15 días (ej: hace 10 días)
4. **Rojo**: Pon una fecha que haya pasado hace >15 días (ej: hace 30 días)
5. Cambia el umbral en Ajustes → "Días para amarillo" para ajustar los límites

---

### 2. **Indicador operativa** (Calculado - Fijo)
- **Verde**: BUY
- **Gris**: HOLD
- **Amarillo**: No aplica
- **Rojo**: SELL

**Cómo probar:**
- Se calcula automáticamente basado en "Cantidad a aumentar/reducir" vs Tier
- **BUY**: Cuando cantidad invertida < Tier - 25%
- **HOLD**: Cuando cantidad invertida está dentro ±25% del Tier
- **SELL**: Cuando cantidad invertida > Tier + 25%

**Para forzar valores:**
- Ajusta el Tier amount en Ajustes (ej: Tier 1 = 500€)
- Asegúrate que el asset esté en cartera con un valor diferente al Tier

---

### 3. **Tier (1-5)** (Calculado - Solo para assets en cartera)
- **Verde**: Desviación ≤ green_pct% (default 25%)
- **Amarillo**: Desviación entre green_pct% y yellow_pct% (default 50%)
- **Rojo**: Desviación > yellow_pct%

**Cómo probar:**
1. Ve a Ajustes → "Tier (desviación del valor del Tier)"
2. Configura: Verde = 25%, Amarillo = 50%
3. **Verde**: 
   - Tier 1 = 500€, cantidad invertida = 480€ (4% de desviación, < 25%)
4. **Amarillo**: 
   - Tier 1 = 500€, cantidad invertida = 350€ (30% de desviación, entre 25-50%)
5. **Rojo**: 
   - Tier 1 = 500€, cantidad invertida = 200€ (60% de desviación, > 50%)

---

### 4. **Cantidad a aumentar/reducir** (Calculado - Fijo)
- **Verde**: Valor positivo (comprar más)
- **Gris**: 0€
- **Rojo**: Valor negativo (vender)

**Cómo probar:**
- Se calcula como: `Cantidad invertida actual - Cantidad del Tier`
- **Verde**: Si tienes 200€ y Tier es 500€ → +300€ (verde)
- **Rojo**: Si tienes 800€ y Tier es 500€ → -300€ (rojo)

---

### 5. **Rentabilidad a 5 años (%)** (Calculado)
- **Verde**: >= green_min (default 60%)
- **Amarillo**: >= yellow_min y < green_min (default 30-60%)
- **Rojo**: < yellow_min (default < 30%)

**Cómo probar:**
1. Ve a Ajustes → "Rentabilidad a 5 años (%)"
2. Configura umbrales (default: Verde ≥ 60, Amarillo ≥ 30)
3. Edita métricas manuales de un asset:
   - **Verde**: Configura valores que den rentabilidad ≥60%:
     - EPS = 5, CAGR = 15%, PER = 20, Dividend Yield = 3%
     - Precio actual = 100
     - Target Price ≈ 421 → Rentabilidad 5yr ≈ 64%
   - **Amarillo**: Configura valores que den rentabilidad 30-60%:
     - EPS = 3, CAGR = 10%, PER = 15, Dividend Yield = 2%
     - Precio actual = 100
     - Target Price ≈ 193 → Rentabilidad 5yr ≈ 38%
   - **Rojo**: Configura valores que den rentabilidad <30%:
     - EPS = 2, CAGR = 5%, PER = 12, Dividend Yield = 1%
     - Precio actual = 100
     - Target Price ≈ 127 → Rentabilidad 5yr ≈ 26%

**Fórmula**: `(Target Price - Precio actual) / Precio actual * 100 + (Dividend Yield * 5)`

---

### 6. **Valoración actual 12 meses (%)** (Calculado)
- **Verde**: >= green_min (default 10%) → Infravalorado (bueno)
- **Amarillo**: >= yellow_min y < green_min (default 0-10%) → Cercano a Fair Value
- **Rojo**: < yellow_min (default < 0%) → Sobrevalorado (malo)

**Cómo probar:**
1. Ve a Ajustes → "Valoración actual 12 meses (%)"
2. Configura umbrales (default: Verde ≥ 10, Amarillo ≥ 0)
3. Edita métricas manuales (solo PER y CAGR, Dividend Yield ya no se usa):
   - **Verde (Infravalorado)**: 
     - PER = 5, Dividend Yield = 2%, CAGR = 10%
     - Cálculo: Denominador = 10+2 = 12, PEGY = 5/12 = 0.42 → (0.42-1)*100 = -58% → Invertido: **+58%** ✅ (Verde, >= 10%)
   - **Amarillo (Fair Value cercano)**: 
     - PER = 10, Dividend Yield = 0%, CAGR = 10%
     - Cálculo: Denominador = 10+0 = 10, PEGY = 10/10 = 1.0 → (1.0-1)*100 = 0% → Invertido: **0%** ✅ (Amarillo, entre 0-10%)
   - **Amarillo (Ligeramente sobrevalorado)**: 
     - PER = 15, Dividend Yield = 5%, CAGR = 10%
     - Cálculo: Denominador = 10+5 = 15, PEGY = 15/15 = 1.0 → (1.0-1)*100 = 0% → Invertido: **0%** ✅ (Amarillo, Fair Value)
   - **Rojo (Sobrevalorado)**: 
     - PER = 15, Dividend Yield = 0%, CAGR = 10%
     - Cálculo: Denominador = 10+0 = 10, PEGY = 15/10 = 1.5 → (1.5-1)*100 = +50% → Invertido: **-50%** ✅ (Rojo, < 0%)

**Fórmula PEGY Ratio**: `-((PER / (CAGR% + Dividend Yield%)) - 1) * 100`
- **Positivo** (ej: +33%): Infravalorado = Verde (bueno)
- **Negativo** (ej: -50%): Sobrevalorado = Rojo (malo)
- **0%**: Fair Value = Amarillo

**Ejemplo con tus datos:**
- PER=10, Dividend Yield=5%, CAGR=10%
- Denominador = 10 + 5 = 15 (Crecimiento + Rendimiento por Dividendo)
- PEGY = 10/15 = 0.67
- (0.67 - 1) * 100 = -33.33%
- Invertido: **+33.33%** → Se muestra como +33% (Verde, infravalorado)

**Ejemplo comparativo (como en tu explicación):**
- PER=15, CAGR=10%, Dividend Yield=0% → PEGY = 15/(10+0) = 1.5 → **-50%** (Rojo, sobrevalorado)
- PER=15, CAGR=10%, Dividend Yield=5% → PEGY = 15/(10+5) = 1.0 → **0%** (Amarillo, Fair Value)

---

### 7. **Rentabilidad Anual (%)** (Calculado)
- **Verde**: >= green_min (default 10%)
- **Amarillo**: >= yellow_min y < green_min (default 0-10%)
- **Rojo**: < yellow_min (default < 0%)

**Cómo probar:**
1. Ve a Ajustes → "Rentabilidad Anual (%)"
2. Configura umbrales (default: Verde ≥ 10, Amarillo ≥ 0)
3. Edita métricas manuales:
   - **Verde**: Mismos valores que Rentabilidad 5 años pero se anualiza
     - Si Rentabilidad 5yr = 64% → Anual ≈ 10.4% ✅
   - **Amarillo**: 
     - Si Rentabilidad 5yr = 38% → Anual ≈ 6.7% ✅
   - **Rojo**: 
     - Si Rentabilidad 5yr = 26% → Anual ≈ 4.7% (sigue siendo positivo)
     - Para rojo necesitas valores que den rentabilidad negativa (Target Price < Precio actual)

**Fórmula**: `(((Target Price / Precio actual)^(1/5)) - 1) * 100 + Dividend Yield`

---

### 8. **Peso en cartera (%)** (Calculado - Solo para assets en cartera)
- **Verde**: (peso - umbral) < green_max_pct (default 10%)
- **Amarillo**: (peso - umbral) entre yellow_min_pct y yellow_max_pct (default 10-25%)
- **Rojo**: (peso - umbral) >= yellow_max_pct (default ≥25%)

**Cómo probar:**
1. Ve a Ajustes → "Umbral máximo peso en cartera" (default 10%)
2. Configura: Verde máx = 10%, Amarillo min = 10%, Amarillo máx = 25%
3. **Verde**: 
   - Umbral = 10%, Peso real = 15% → (15-10) = 5% < 10% ✅
4. **Amarillo**: 
   - Umbral = 10%, Peso real = 18% → (18-10) = 8% (no, esto sigue siendo <10%)
   - Umbral = 10%, Peso real = 20% → (20-10) = 10% ✅ (entre 10-25%)
5. **Rojo**: 
   - Umbral = 10%, Peso real = 38% → (38-10) = 28% ≥ 25% ✅

**Nota**: El peso se calcula automáticamente desde tus holdings, no se puede editar manualmente.

---

## 🧪 Script de Prueba Rápida

Para probar rápidamente, puedes editar directamente en la base de datos o usar el modal de edición:

### Casos de Prueba Recomendados:

**Asset de Prueba 1 - Todo Verde:**
- Fecha resultados: `2025-12-31` (futuro)
- PER: 25, Dividend Yield: 3%, CAGR: 20%, EPS: 5
- Precio actual: 100
- Resultado esperado:
  - Valoración 12m: 140% (Verde)
  - Target Price: 420
  - Rentabilidad 5yr: ~64% (Verde)
  - Rentabilidad Anual: ~10.4% (Verde)

**Asset de Prueba 2 - Todo Amarillo:**
- Fecha resultados: Hace 10 días (dentro del límite amarillo)
- PER: 12, Dividend Yield: 2%, CAGR: 15%, EPS: 3
- Precio actual: 100
- Resultado esperado:
  - Valoración 12m: 9.3% (Amarillo)
  - Target Price: 193
  - Rentabilidad 5yr: ~38% (Amarillo)
  - Rentabilidad Anual: ~6.7% (Amarillo)

**Asset de Prueba 3 - Todo Rojo:**
- Fecha resultados: Hace 30 días (fuera del límite)
- PER: 10, Dividend Yield: 1%, CAGR: 12%, EPS: 2
- Precio actual: 150
- Resultado esperado:
  - Valoración 12m: 9.2% (Amarillo, no rojo - la fórmula no da negativos normalmente)
  - Target Price: 127
  - Rentabilidad 5yr: ~-10% (Rojo - negativo)
  - Rentabilidad Anual: ~-2% (Rojo)

---

## 📊 Tabla de Referencia Rápida

### Valores de Entrada → Resultados Esperados

| Objetivo | PER | Div. Yield | CAGR | EPS | Precio Actual | Target Price | Valoración 12m | Rent. 5yr | Rent. Anual |
|----------|-----|------------|------|-----|---------------|--------------|----------------|-----------|-------------|
| **Valoración VERDE (≥10%, infravalorado)** | 5 | 2% | 10% | 5 | 100 | 421 | **+58%** ✅ | 64% | 10.4% |
| **Valoración AMARILLO (0-10%, fair value)** | 15 | 5% | 10% | 3 | 100 | 193 | **0%** ✅ | 38% | 6.7% |
| **Valoración ROJO (<0%, sobrevalorado)** | 15 | 0% | 10% | 2 | 100 | 98 | **-50%** ✅ | -2% | -0.4% |
| **Rent. 5yr VERDE (≥60%)** | 25 | 3% | 20% | 5 | 100 | 421 | 140% | **64%** ✅ | 10.4% |
| **Rent. 5yr AMARILLO (30-60%)** | 15 | 2% | 12% | 4 | 100 | 221 | 142% | **48%** ✅ | 8.2% |
| **Rent. 5yr ROJO (<30%)** | 12 | 1% | 10% | 3 | 100 | 145 | 130% | **20%** ✅ | 3.7% |
| **Rent. Anual VERDE (≥10%)** | 25 | 3% | 20% | 5 | 100 | 421 | 140% | 64% | **10.4%** ✅ |
| **Rent. Anual AMARILLO (0-10%)** | 15 | 2% | 12% | 4 | 100 | 221 | 142% | 48% | **8.2%** ✅ |
| **Rent. Anual ROJO (<0%)** | 10 | 1% | 8% | 2 | 100 | 80 | 138% | -20% | **-4.3%** ✅ |

**Fórmulas:**
- **Target Price** = `EPS * (1 + CAGR%)^5 * PER`
- **Valoración 12m** = `((PER + Div.Yield%) / CAGR%) * 100`
- **Rent. 5yr** = `((Target - Precio) / Precio) * 100 + (Div.Yield * 5)`
- **Rent. Anual** = `(((Target/Precio)^(1/5)) - 1) * 100 + Div.Yield`

### Para Peso en Cartera

| Umbral Base | Peso Real | Diferencia | Color Esperado |
|-------------|-----------|------------|----------------|
| 10% | 15% | +5% | Verde (< 10%) ✅ |
| 10% | 20% | +10% | Amarillo (10-25%) ✅ |
| 10% | 18% | +8% | Verde (< 10%) ⚠️ |
| 10% | 35% | +25% | Rojo (≥ 25%) ✅ |

### Para Tier

**Ejemplo con Tier 1 = 500€:**

| Cantidad Invertida | Desviación | Desviación % | Color Esperado |
|-------------------|------------|--------------|----------------|
| 480€ | 20€ | 4% | Verde (≤25%) ✅ |
| 375€ | 125€ | 25% | Verde (≤25%) ✅ |
| 350€ | 150€ | 30% | Amarillo (25-50%) ✅ |
| 250€ | 250€ | 50% | Amarillo (25-50%) ✅ |
| 200€ | 300€ | 60% | Rojo (>50%) ✅ |

## ✅ Checklist de Prueba

- [ ] Fecha resultados: Verde (futuro)
- [ ] Fecha resultados: Amarillo (pasado reciente)
- [ ] Fecha resultados: Rojo (pasado lejano)
- [ ] Indicador operativa: BUY (verde)
- [ ] Indicador operativa: HOLD (gris)
- [ ] Indicador operativa: SELL (rojo)
- [ ] Tier: Verde (dentro del rango)
- [ ] Tier: Amarillo (desviación media)
- [ ] Tier: Rojo (desviación alta)
- [ ] Cantidad a aumentar/reducir: Verde (positivo)
- [ ] Cantidad a aumentar/reducir: Rojo (negativo)
- [ ] Rentabilidad 5 años: Verde (≥60%)
- [ ] Rentabilidad 5 años: Amarillo (30-60%)
- [ ] Rentabilidad 5 años: Rojo (<30%)
- [ ] Valoración 12m: Verde (≥10%)
- [ ] Valoración 12m: Amarillo (0-10%)
- [ ] Valoración 12m: Rojo (<0% - si es posible)
- [ ] Rentabilidad Anual: Verde (≥10%)
- [ ] Rentabilidad Anual: Amarillo (0-10%)
- [ ] Rentabilidad Anual: Rojo (<0%)
- [ ] Peso en cartera: Verde (< umbral + 10%)
- [ ] Peso en cartera: Amarillo (umbral + 10% a 25%)
- [ ] Peso en cartera: Rojo (≥ umbral + 25%)

