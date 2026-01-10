# 📊 Explicación: Cálculo del Tier (1-5)

## ¿Qué es el Tier?

El **Tier** indica el **tamaño de posición recomendado** para un activo según su valoración actual. Va del 1 al 5, donde:
- **Tier 5** = Mayor posición (mejor oportunidad de inversión, muy infravalorado)
- **Tier 4** = Posición grande
- **Tier 3** = Posición media
- **Tier 2** = Posición pequeña
- **Tier 1** = Posición muy pequeña o evitar (sobrevalorado)

---

## ¿Cómo se calcula el Tier?

El Tier se calcula **automáticamente** basándose en la **Valoración 12m (%)** del activo.

### Paso 1: Calcular Valoración 12m (%)

Primero se calcula la **Valoración actual 12 meses (%)** usando la fórmula **PEGY Ratio**:

```
Valoración 12m = -((PER / (CAGR% + Dividend Yield%)) - 1) * 100
```

**Ejemplos:**
- PER=5, CAGR=10%, Div Yield=2% → PEGY=5/(10+2)=0.42 → Valoración = **+58%** ✅ (muy infravalorado)
- PER=10, CAGR=10%, Div Yield=0% → PEGY=10/10=1.0 → Valoración = **0%** ⚠️ (fair value)
- PER=15, CAGR=10%, Div Yield=0% → PEGY=15/10=1.5 → Valoración = **-50%** ❌ (sobrevalorado)

### Paso 2: Asignar Tier según Rangos

El sistema compara la **Valoración 12m (%)** con los **rangos configurables** de cada Tier:

#### Rangos por Defecto:

| Tier | Rango de Valoración 12m | Interpretación |
|------|------------------------|----------------|
| **Tier 5** | ≥ 50% | Muy infravalorado → Mayor posición (ej: 10,000€) |
| **Tier 4** | 30% - 50% | Infravalorado → Posición grande (ej: 5,000€) |
| **Tier 3** | 10% - 30% | Ligeramente infravalorado → Posición media (ej: 2,000€) |
| **Tier 2** | 0% - 10% | Cerca de fair value → Posición pequeña (ej: 1,000€) |
| **Tier 1** | < 0% | Sobrevalorado → Posición mínima (ej: 500€) |

#### Algoritmo de Asignación:

1. El sistema prueba desde **Tier 5** (mayor) hasta **Tier 1** (menor)
2. Para cada Tier, verifica si la **Valoración 12m** está dentro de su rango:
   - Si tiene `min`: Valoración debe ser **≥ min**
   - Si tiene `max`: Valoración debe ser **< max**
3. Asigna el **primer Tier** que coincida

**Ejemplo:**
- Valoración 12m = **+35%**
  - Tier 5: ¿35% ≥ 50%? ❌ No
  - Tier 4: ¿35% ≥ 30% Y 35% < 50%? ✅ **Sí** → **Tier 4**

---

## Configuración de Rangos

Los rangos del Tier son **configurables por el usuario** en **Ajustes**:

1. Ve a `/portfolio/watchlist` → Botón **"Ajustes"** (⚙️)
2. Sección **"Rangos de Tier"**
3. Define los rangos mínimos y máximos para cada Tier (1-5)

**Formato:**
- `tier_5`: Solo `min` (ej: 50.0) → Valoración ≥ 50%
- `tier_4`: `min` y `max` (ej: min=30.0, max=50.0) → 30% ≤ Valoración < 50%
- `tier_3`: `min` y `max` (ej: min=10.0, max=30.0) → 10% ≤ Valoración < 30%
- `tier_2`: `min` y `max` (ej: min=0.0, max=10.0) → 0% ≤ Valoración < 10%
- `tier_1`: Solo `max` (ej: max=0.0) → Valoración < 0%

---

## Configuración de Cantidades por Tier

Además de los rangos, el usuario puede definir **cantidades absolutas en EUR** para cada Tier:

| Tier | Cantidad por Defecto | Ejemplo |
|------|---------------------|---------|
| Tier 1 | 500€ | Si Tier=1, deberías tener 500€ invertidos |
| Tier 2 | 1,000€ | Si Tier=2, deberías tener 1,000€ invertidos |
| Tier 3 | 2,000€ | Si Tier=3, deberías tener 2,000€ invertidos |
| Tier 4 | 5,000€ | Si Tier=4, deberías tener 5,000€ invertidos |
| Tier 5 | 10,000€ | Si Tier=5, deberías tener 10,000€ invertidos |

Estas cantidades se configuran en **Ajustes** → **"Tier amounts"**

---

## Colores del Tier

Los colores del Tier se muestran **solo para assets en cartera** y dependen de la **desviación** entre la cantidad invertida actual y el Tier amount:

### Verde (dentro del rango)
- Desviación ≤ 25% del Tier amount
- **Ejemplo:** Tier 1 = 500€, Tienes 480€ → Desviación = 4% → ✅ Verde

### Amarillo (desviación media)
- Desviación entre 25% y 50% del Tier amount
- **Ejemplo:** Tier 1 = 500€, Tienes 350€ → Desviación = 30% → ⚠️ Amarillo

### Rojo (desviación alta)
- Desviación > 50% del Tier amount
- **Ejemplo:** Tier 1 = 500€, Tienes 200€ → Desviación = 60% → ❌ Rojo

**Fórmula de desviación:**
```
Desviación % = |Cantidad Invertida - Tier Amount| / Tier Amount * 100
```

---

## Flujo Completo

1. **Usuario edita métricas manuales** (PER, CAGR, Dividend Yield, EPS)
2. **Sistema calcula Valoración 12m** usando fórmula PEGY
3. **Sistema compara Valoración 12m** con rangos configurables
4. **Sistema asigna Tier** (1-5) automáticamente
5. **Si el asset está en cartera:**
   - Sistema calcula desviación entre cantidad invertida y Tier amount
   - Sistema muestra color (Verde/Amarillo/Rojo) según desviación
6. **Sistema calcula "Cantidad a aumentar/reducir"** = Cantidad Actual - Tier Amount
7. **Sistema calcula "Indicador operativa"** (BUY/SELL/HOLD) basado en la cantidad a aumentar/reducir

---

## Ejemplo Práctico Completo

**Asset:** Empresa ABC
- **PER:** 7
- **CAGR:** 10%
- **Dividend Yield:** 3%
- **Cantidad invertida actual:** 1,200€

**Cálculo:**
1. **Valoración 12m:**
   - PEGY = 7 / (10 + 3) = 7 / 13 = 0.54
   - Valoración = -(0.54 - 1) * 100 = **+46%** ✅

2. **Tier asignado:**
   - Valoración = 46%
   - Tier 5: ¿46% ≥ 50%? ❌ No
   - Tier 4: ¿46% ≥ 30% Y 46% < 50%? ✅ **Sí** → **Tier 4**

3. **Tier Amount:**
   - Tier 4 = 5,000€ (configurado en Ajustes)

4. **Desviación:**
   - Desviación = |1,200€ - 5,000€| / 5,000€ * 100 = 76% ❌

5. **Color del Tier:**
   - Desviación 76% > 50% → **Rojo** ❌

6. **Cantidad a aumentar/reducir:**
   - 1,200€ - 5,000€ = **-3,800€** (necesitas comprar 3,800€ más)

7. **Indicador operativa:**
   - Como cantidad < Tier - 25% (1,200 < 3,750) → **BUY** ✅

---

## Resumen

- ✅ **Tier se calcula automáticamente** basado en Valoración 12m (%)
- ✅ **Rangos son configurables** por el usuario en Ajustes
- ✅ **Cantidades por Tier son configurables** por el usuario en Ajustes
- ✅ **Colores del Tier** muestran qué tan cerca estás del Tier amount recomendado
- ✅ **Indicador operativa** (BUY/SELL/HOLD) se basa en la diferencia con el Tier amount

