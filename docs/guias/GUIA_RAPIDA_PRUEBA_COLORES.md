# 🚀 Guía Rápida - Prueba de Colores Watchlist

## 📝 Pasos para Probar Todos los Colores

### **PASO 1: Configurar Umbrales en Ajustes**

1. Ve a `/portfolio/watchlist`
2. Click en botón **"Ajustes"** (⚙️)
3. Configura los siguientes umbrales (o usa los valores por defecto):
   - **Valoración 12m**: Verde ≥ 10, Amarillo ≥ 0
   - **Rentabilidad 5 años**: Verde ≥ 60, Amarillo ≥ 30
   - **Rentabilidad Anual**: Verde ≥ 10, Amarillo ≥ 0
   - **Tier**: Verde 25%, Amarillo 50%
   - **Peso cartera**: Verde máx 10%, Amarillo min 10%, Amarillo máx 25%
   - **Fecha resultados**: 15 días
   - **Tier amounts**: Tier 1=500€, Tier 2=1000€, Tier 3=2000€, Tier 4=5000€, Tier 5=10000€
4. Click **"Guardar Ajustes"**

---

### **PASO 2: Crear Assets de Prueba**

#### **Asset Prueba 1: Todo Verde** ✅

1. Añade un asset nuevo (desde Yahoo o AssetRegistry)
2. Edita métricas (✏️) y configura:
   - **Fecha próximos resultados**: `2025-12-31` (futuro → Verde)
   - **PER**: `5`
   - **NTM Dividend Yield**: `3` (no se usa en valoración, pero para rentabilidades)
   - **EPS**: `5`
   - **CAGR Revenue YoY**: `10`
   - Guarda

**Resultado esperado:**
- ✅ Fecha resultados: **Verde** (futuro)
- ✅ Valoración 12m: **Verde** (+50% ≥ 10%, infravalorado = bueno)
- ✅ Rentabilidad 5yr: **Verde** (si se calcula correctamente)
- ✅ Rentabilidad Anual: **Verde** (si se calcula correctamente)

#### **Asset Prueba 2: Todo Amarillo** ⚠️

1. Añade otro asset
2. Edita métricas:
   - **Fecha próximos resultados**: Hace 10 días (ej: si hoy es 2025-01-15, usa `2025-01-05`)
   - **PER**: `10`
   - **NTM Dividend Yield**: `2`
   - **EPS**: `3`
   - **CAGR Revenue YoY**: `10`
   - Guarda

**Resultado esperado:**
- ⚠️ Fecha resultados: **Amarillo** (pasado reciente)
- ⚠️ Valoración 12m: **Amarillo** (0% entre 0-10%, fair value)
- ⚠️ Rentabilidad 5yr: **Amarillo** (si está entre 30-60%)
- ⚠️ Rentabilidad Anual: **Amarillo** (si está entre 0-10%)

#### **Asset Prueba 3: Todo Rojo** ❌

1. Añade otro asset
2. Edita métricas:
   - **Fecha próximos resultados**: Hace 30 días (ej: `2024-12-15`)
   - **PER**: `15`
   - **NTM Dividend Yield**: `1`
   - **EPS**: `2`
   - **CAGR Revenue YoY**: `10`
   - Guarda
3. **IMPORTANTE**: Para que Rentabilidad sea roja, necesitas que Target Price < Precio actual
   - Asegúrate que el precio actual del asset sea mayor que el Target Price calculado
   - O edita el precio actual manualmente si es necesario

**Resultado esperado:**
- ❌ Fecha resultados: **Rojo** (pasado lejano)
- ❌ Valoración 12m: **Rojo** (-50% < 0%, sobrevalorado = malo)
- ❌ Rentabilidad 5yr: **Rojo** (< 30% o negativa)
- ❌ Rentabilidad Anual: **Rojo** (< 0% si es negativa)

---

### **PASO 3: Probar Tier y Peso en Cartera** 💼

**Esto solo funciona para assets que ESTÁN en tu cartera:**

1. Asegúrate de tener assets en tu cartera
2. Ve a Ajustes → Configura Tier amounts (ej: Tier 1 = 500€)
3. Edita las métricas de un asset en cartera para que:
   - El Tier calculado sea Tier 1 (ej: Valoración 12m < 0%)
   - La cantidad invertida actual sea diferente al Tier amount

**Casos de prueba Tier:**
- **Verde**: Si tienes 480€ y Tier 1 = 500€ → desviación 4% (≤25%)
- **Amarillo**: Si tienes 350€ y Tier 1 = 500€ → desviación 30% (25-50%)
- **Rojo**: Si tienes 200€ y Tier 1 = 500€ → desviación 60% (>50%)

**Casos de prueba Peso en cartera:**
- Necesitas que un asset tenga un peso específico en tu portfolio
- **Verde**: Peso < (umbral + 10%), ej: Umbral=10%, Peso=15% → (15-10)=5% < 10% ✅
- **Amarillo**: Peso entre (umbral+10%) y (umbral+25%), ej: Umbral=10%, Peso=20% → (20-10)=10% ✅
- **Rojo**: Peso ≥ (umbral + 25%), ej: Umbral=10%, Peso=38% → (38-10)=28% ≥ 25% ✅

---

### **PASO 4: Probar Indicador Operativa** 🎯

El indicador se calcula automáticamente basado en la diferencia entre cantidad invertida y Tier amount:

1. Asegúrate de tener un asset en cartera
2. Configura Tier amounts en Ajustes
3. **BUY (Verde)**: 
   - Cantidad invertida < Tier amount - 25%
   - Ej: Tier 1 = 500€, Tienes 300€ → +200€ (BUY)
4. **HOLD (Gris)**:
   - Cantidad invertida dentro ±25% del Tier
   - Ej: Tier 1 = 500€, Tienes 480€ (dentro del rango)
5. **SELL (Rojo)**:
   - Cantidad invertida > Tier amount + 25%
   - Ej: Tier 1 = 500€, Tienes 700€ → -200€ (SELL)

---

## 🔍 Verificación Visual

Después de configurar los assets de prueba, deberías ver en la tabla:

| Columna | Asset 1 (Verde) | Asset 2 (Amarillo) | Asset 3 (Rojo) |
|---------|----------------|-------------------|----------------|
| Fecha resultados | 🟢 Verde | 🟡 Amarillo | 🔴 Rojo |
| Indicador operativa | 🟢 BUY / 🔴 SELL / ⚪ HOLD | 🟢 BUY / 🔴 SELL / ⚪ HOLD | 🟢 BUY / 🔴 SELL / ⚪ HOLD |
| Tier | 🟢 (si en rango) | 🟡 (desviación media) | 🔴 (desviación alta) |
| Rent. 5 años | 🟢 ≥60% | 🟡 30-60% | 🔴 <30% |
| Valoración 12m | 🟢 ≥10% | 🟡 0-10% | 🟡/🔴 <10% |
| Rent. Anual | 🟢 ≥10% | 🟡 0-10% | 🔴 <0% |
| Peso cartera | 🟢 < umbral+10% | 🟡 umbral+10-25% | 🔴 ≥ umbral+25% |

---

## ⚠️ Notas Importantes

1. **Valoración 12m normalmente no es negativa**: La fórmula `((PER + Div.Yield) / CAGR) * 100` normalmente da valores positivos. Para rojo, necesitarías valores muy específicos (CAGR muy alto, PER muy bajo).

2. **Rentabilidades negativas**: Para obtener rentabilidades negativas (rojo), necesitas que el Target Price sea menor que el Precio actual. Esto se puede lograr:
   - Configurando un PER muy bajo
   - Configurando un CAGR muy bajo
   - O asegurándote que el precio actual del asset sea alto comparado con el Target Price calculado

3. **Peso en cartera**: Este valor se calcula automáticamente desde tus holdings. No se puede editar manualmente. Para probarlo, necesitas tener assets con diferentes pesos en tu portfolio.

4. **Tier**: Solo muestra colores si el asset está en tu cartera. Si está solo en watchlist, se muestra en gris.

---

## ✅ Checklist Final

- [ ] Configurar umbrales en Ajustes
- [ ] Crear Asset 1 (todo verde)
- [ ] Crear Asset 2 (todo amarillo)  
- [ ] Crear Asset 3 (todo rojo)
- [ ] Verificar colores en la tabla
- [ ] Probar cambiar umbrales y ver cómo cambian los colores
- [ ] Probar Tier con assets en cartera
- [ ] Probar Peso en cartera con diferentes holdings
- [ ] Probar Fecha resultados con diferentes fechas

