# ✅ Checklist de Prueba de Colores - Watchlist

## 📋 Columnas con Colores a Probar

1. ✅ **Fecha próximos resultados** (Verde/Amarillo/Rojo)
2. ✅ **Indicador operativa** (BUY=Verde, HOLD=Gris, SELL=Rojo)
3. ✅ **Tier (1-5)** (Verde/Amarillo/Rojo - solo assets en cartera)
4. ✅ **Rentabilidad a 5 años (%)** (Verde ≥60% / Amarillo 30-60% / Rojo <30%)
5. ✅ **Valoración 12m (%)** (Verde ≥10% / Amarillo 0-10% / Rojo <0%)
6. ✅ **Rentabilidad Anual (%)** (Verde ≥10% / Amarillo 0-10% / Rojo <0%)
7. ✅ **Peso en cartera (%)** (Verde/Amarillo/Rojo según umbral)

---

## 🚀 PASO 1: Configurar Ajustes

- [ ] Ir a `/portfolio/watchlist`
- [ ] Click en botón **"Ajustes"** (⚙️)
- [ ] Verificar/Configurar umbrales:
  - [ ] **Valoración 12m**: Verde ≥ 10%, Amarillo ≥ 0%
  - [ ] **Rentabilidad 5 años**: Verde ≥ 60%, Amarillo ≥ 30%
  - [ ] **Rentabilidad Anual**: Verde ≥ 10%, Amarillo ≥ 0%
  - [ ] **Tier**: Verde ≤ 25%, Amarillo ≤ 50%
  - [ ] **Peso cartera**: Verde máx 10%, Amarillo min 10%, Amarillo máx 25%
  - [ ] **Fecha resultados**: 15 días
  - [ ] **Tier amounts**: Tier 1=500€, Tier 2=1000€, Tier 3=2000€, Tier 4=5000€, Tier 5=10000€
- [ ] Click **"Guardar Ajustes"**
- [ ] Verificar mensaje de confirmación ✅

---

## 🟢 PASO 2: Probar Fecha próximos resultados

### Verde (Futuro)
- [ ] Añadir/Editar un asset
- [ ] Fecha próximos resultados: `2025-12-31` (futuro)
- [ ] Guardar
- [ ] Verificar: **Verde** ✅

### Amarillo (Pasado reciente)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Fecha próximos resultados: Hace 10 días (ej: `2025-01-01` si hoy es `2025-01-11`)
- [ ] Guardar
- [ ] Verificar: **Amarillo** ⚠️

### Rojo (Pasado lejano)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Fecha próximos resultados: Hace 30 días (ej: `2024-12-10`)
- [ ] Guardar
- [ ] Verificar: **Rojo** ❌

---

## 🎯 PASO 3: Probar Indicador Operativa

**Nota:** Solo funciona para assets EN CARRERA (con cantidad invertida)

### BUY (Verde)
- [ ] Asegurarse de tener un asset en cartera
- [ ] Configurar Tier amounts en Ajustes (ej: Tier 1 = 500€)
- [ ] Editar métricas para que el Tier calculado sea Tier 1
- [ ] Verificar que cantidad invertida < Tier - 25%
  - Ej: Tier 1 = 500€, Tienes 300€ → **BUY (Verde)** ✅

### HOLD (Gris)
- [ ] Mismo asset o crear uno nuevo
- [ ] Ajustar cantidad invertida para que esté dentro ±25% del Tier
  - Ej: Tier 1 = 500€, Tienes 480€ → **HOLD (Gris)** ⚪

### SELL (Rojo)
- [ ] Mismo asset o crear uno nuevo
- [ ] Ajustar cantidad invertida para que sea > Tier + 25%
  - Ej: Tier 1 = 500€, Tienes 700€ → **SELL (Rojo)** ❌

---

## 🏆 PASO 4: Probar Tier (1-5)

**Nota:** Solo muestra colores para assets EN CARRERA

### Verde (Desviación ≤ 25%)
- [ ] Asset en cartera con Tier asignado
- [ ] Tier 1 = 500€, cantidad invertida = 480€ (4% desviación)
- [ ] Verificar: **Tier en Verde** ✅

### Amarillo (Desviación 25-50%)
- [ ] Mismo asset o crear uno nuevo
- [ ] Tier 1 = 500€, cantidad invertida = 350€ (30% desviación)
- [ ] Verificar: **Tier en Amarillo** ⚠️

### Rojo (Desviación > 50%)
- [ ] Mismo asset o crear uno nuevo
- [ ] Tier 1 = 500€, cantidad invertida = 200€ (60% desviación)
- [ ] Verificar: **Tier en Rojo** ❌

---

## 💰 PASO 5: Probar Rentabilidad a 5 años (%)

### Verde (≥ 60%)
- [ ] Añadir/Editar un asset
- [ ] Configurar: PER alto, CAGR alto, EPS alto, Dividend Yield
  - Ej: PER=25, CAGR=20%, EPS=5, Dividend Yield=3%
- [ ] Guardar
- [ ] Verificar: **Rentabilidad 5yr ≥ 60% en Verde** ✅

### Amarillo (30-60%)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Configurar valores intermedios
  - Ej: PER=15, CAGR=10%, EPS=3, Dividend Yield=2%
- [ ] Guardar
- [ ] Verificar: **Rentabilidad 5yr entre 30-60% en Amarillo** ⚠️

### Rojo (< 30%)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Configurar valores bajos o negativos
  - Ej: PER=10, CAGR=5%, EPS=2, Dividend Yield=1%
  - O asegurar que Target Price < Precio actual
- [ ] Guardar
- [ ] Verificar: **Rentabilidad 5yr < 30% en Rojo** ❌

---

## 📊 PASO 6: Probar Valoración 12m (%) - PEGY Ratio

### Verde (≥ 10% - Infravalorado)
- [ ] Añadir/Editar un asset
- [ ] Configurar: PER bajo, CAGR alto, Dividend Yield
  - Ej: PER=5, CAGR=10%, Dividend Yield=2%
  - PEGY = 5/(10+2) = 0.42 → +58% ✅
- [ ] Guardar
- [ ] Verificar: **Valoración 12m ≥ 10% en Verde** ✅

### Amarillo (0-10% - Fair Value cercano)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Configurar: PER y CAGR balanceados
  - Ej: PER=10, CAGR=10%, Dividend Yield=0%
  - PEGY = 10/(10+0) = 1.0 → 0% ✅
- [ ] Guardar
- [ ] Verificar: **Valoración 12m entre 0-10% en Amarillo** ⚠️

### Rojo (< 0% - Sobrevalorado)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Configurar: PER alto, CAGR bajo, Dividend Yield bajo
  - Ej: PER=15, CAGR=10%, Dividend Yield=0%
  - PEGY = 15/(10+0) = 1.5 → -50% ✅
- [ ] Guardar
- [ ] Verificar: **Valoración 12m < 0% en Rojo** ❌

---

## 📈 PASO 7: Probar Rentabilidad Anual (%)

### Verde (≥ 10%)
- [ ] Añadir/Editar un asset
- [ ] Configurar valores que den rentabilidad alta
  - Ej: PER alto, CAGR alto, EPS alto, Dividend Yield alto
- [ ] Guardar
- [ ] Verificar: **Rentabilidad Anual ≥ 10% en Verde** ✅

### Amarillo (0-10%)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Configurar valores intermedios
- [ ] Guardar
- [ ] Verificar: **Rentabilidad Anual entre 0-10% en Amarillo** ⚠️

### Rojo (< 0%)
- [ ] Editar el mismo asset o crear uno nuevo
- [ ] Configurar valores que den rentabilidad negativa
  - Asegurar que Target Price < Precio actual
- [ ] Guardar
- [ ] Verificar: **Rentabilidad Anual < 0% en Rojo** ❌

---

## ⚖️ PASO 8: Probar Peso en cartera (%)

**Nota:** Solo funciona para assets EN CARRERA. El peso se calcula automáticamente.

### Verde (< umbral + 10%)
- [ ] Asegurarse de tener assets en cartera
- [ ] Configurar umbral máximo en Ajustes (ej: 10%)
- [ ] Verificar asset con peso < 20% (si umbral=10%, entonces 20-10=10% < 10%... espera, esto está mal)
- [ ] **Corrección:** Verde si peso < (umbral + 10%)
  - Si umbral=10%, Verde si peso < 20%
  - Ej: Peso = 15% → (15-10)=5% < 10% ✅ Verde

### Amarillo (umbral+10% ≤ peso < umbral+25%)
- [ ] Mismo asset o verificar otro
- [ ] Si umbral=10%, Amarillo si peso entre 20% y 35%
  - Ej: Peso = 25% → (25-10)=15% entre 10-25% ✅ Amarillo

### Rojo (peso ≥ umbral + 25%)
- [ ] Mismo asset o verificar otro
- [ ] Si umbral=10%, Rojo si peso ≥ 35%
  - Ej: Peso = 38% → (38-10)=28% ≥ 25% ✅ Rojo

---

## 🎨 PASO 9: Verificación Visual Completa

Crear 3 assets de prueba que muestren todos los colores:

### Asset 1: Todo Verde ✅
- [ ] Fecha resultados: Futuro
- [ ] Indicador: BUY (si está en cartera)
- [ ] Tier: Verde (si está en cartera y dentro del rango)
- [ ] Rentabilidad 5yr: ≥ 60%
- [ ] Valoración 12m: ≥ 10%
- [ ] Rentabilidad Anual: ≥ 10%
- [ ] Peso cartera: Verde (si está en cartera)

### Asset 2: Todo Amarillo ⚠️
- [ ] Fecha resultados: Pasado reciente (≤15 días)
- [ ] Indicador: HOLD (si está en cartera)
- [ ] Tier: Amarillo (si está en cartera, desviación media)
- [ ] Rentabilidad 5yr: 30-60%
- [ ] Valoración 12m: 0-10%
- [ ] Rentabilidad Anual: 0-10%
- [ ] Peso cartera: Amarillo (si está en cartera)

### Asset 3: Todo Rojo ❌
- [ ] Fecha resultados: Pasado lejano (>15 días)
- [ ] Indicador: SELL (si está en cartera)
- [ ] Tier: Rojo (si está en cartera, desviación alta)
- [ ] Rentabilidad 5yr: < 30%
- [ ] Valoración 12m: < 0%
- [ ] Rentabilidad Anual: < 0%
- [ ] Peso cartera: Rojo (si está en cartera)

---

## 🔄 PASO 10: Probar Cambio de Umbrales

- [ ] Ir a Ajustes
- [ ] Cambiar umbral de "Valoración 12m" Verde de 10% a 20%
- [ ] Guardar
- [ ] Verificar que los colores cambian en la tabla
- [ ] Cambiar umbral de "Rentabilidad 5 años" Verde de 60% a 50%
- [ ] Guardar
- [ ] Verificar que los colores cambian
- [ ] Restaurar valores por defecto

---

## ✅ Checklist Final

- [ ] Todas las columnas con colores probadas
- [ ] Todos los estados de color verificados (Verde/Amarillo/Rojo)
- [ ] Cambio de umbrales funciona correctamente
- [ ] Assets en cartera muestran colores correctos
- [ ] Assets solo en watchlist muestran colores correctos
- [ ] Tooltips funcionan en todas las columnas calculadas
- [ ] No hay errores en consola del navegador
- [ ] La página se recarga correctamente después de guardar

---

## 📝 Notas

1. **Valoración 12m**: Usa la fórmula PEGY Ratio: `-((PER / (CAGR + Dividend Yield)) - 1) * 100`
2. **Rentabilidades negativas**: Para obtener rojo, necesitas Target Price < Precio actual
3. **Peso en cartera**: Se calcula automáticamente desde holdings, no se puede editar manualmente
4. **Tier e Indicador operativa**: Solo funcionan para assets en cartera

