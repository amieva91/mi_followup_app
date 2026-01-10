# 🎨 CHECKLIST PRUEBA DE COLORES - WATCHLIST

## Guía de Pruebas Columna por Columna

### 1. **FECHA PRÓXIMOS RESULTADOS** 📅
**Configuración**: Umbral configurable en Ajustes (por defecto: 15 días)

- [ ] **Verde**: Fecha futura (aún no ha pasado)
  - Ejemplo: Fecha = 2026-02-01 (futura) → Verde
- [ ] **Amarillo**: Fecha pasada pero ≤ 15 días desde hoy
  - Ejemplo: Fecha = hace 10 días → Amarillo
- [ ] **Rojo**: Fecha pasada > 15 días desde hoy
  - Ejemplo: Fecha = hace 20 días → Rojo

**Cómo probar**: 
1. Editar un asset y cambiar la fecha de próximos resultados
2. Probar con fechas futuras, recientes (≤15 días) y antiguas (>15 días)

---

### 2. **INDICADOR OPERATIVA** (BUY/SELL/HOLD) 🎯
**Lógica**: Calculado automáticamente según Cantidad a aumentar/reducir

- [ ] **Verde (BUY)**: Cantidad a aumentar > 0
  - Ejemplo: Cantidad = +1.436€ → BUY (verde)
- [ ] **Gris (HOLD)**: Cantidad a aumentar/reducir ≈ 0 (dentro del margen)
  - Ejemplo: Cantidad = 0€ o muy cercana a 0 → HOLD (gris)
- [ ] **Rojo (SELL)**: Cantidad a aumentar < 0 (hay que vender)
  - Ejemplo: Cantidad = -1.436€ → SELL (rojo)

**Cómo probar**: 
1. Modificar el Tier de un asset en cartera para cambiar la cantidad
2. Aumentar Tier → debería mostrar BUY
3. Disminuir Tier → debería mostrar SELL
4. Tier = valor actual → debería mostrar HOLD

---

### 3. **TIER (1-5)** 🎚️
**Configuración**: Umbrales configurables en Ajustes (por defecto: Verde ≤25%, Amarillo ≤50%)
**Aplica solo a**: Assets en cartera (con `current_value_eur`)

- [ ] **Verde**: Desviación ≤ 25% del Tier amount configurado
  - Ejemplo: Tier 3 = 3.936€, Valor actual = 4.000€ (desviación 1.6%) → Verde
- [ ] **Amarillo**: Desviación > 25% pero ≤ 50%
  - Ejemplo: Tier 3 = 3.936€, Valor actual = 5.000€ (desviación 27%) → Amarillo
- [ ] **Rojo**: Desviación > 50%
  - Ejemplo: Tier 3 = 3.936€, Valor actual = 6.000€ (desviación 52%) → Rojo

**Cómo probar**: 
1. Abrir Ajustes y configurar Tier amounts
2. Verificar assets en cartera con diferentes desviaciones
3. Modificar Tier amount para forzar diferentes estados de color

---

### 4. **CANTIDAD A AUMENTAR/REDUCIR** 💰
**Lógica**: `current_value_eur - tier_amount`

- [ ] **Verde**: Valor positivo (hay que comprar más)
  - Ejemplo: +1.436€ → Verde
- [ ] **Rojo**: Valor negativo (hay que vender)
  - Ejemplo: -1.436€ → Rojo

**Cómo probar**: 
1. Modificar Tier amount para forzar valores positivos/negativos
2. Verificar que los colores se aplican correctamente

---

### 5. **RENT. 5 AÑOS (%)** 📈
**Configuración**: Umbrales configurables en Ajustes (por defecto: Verde ≥60%, Amarillo ≥30%, Rojo <30%)

- [ ] **Verde**: Rentabilidad ≥ umbral verde (por defecto ≥60%)
  - Ejemplo: 166.5% → Verde
- [ ] **Amarillo**: Rentabilidad ≥ umbral amarillo pero < umbral verde (por defecto ≥30% y <60%)
  - Ejemplo: 45% → Amarillo
- [ ] **Rojo**: Rentabilidad < umbral amarillo (por defecto <30%)
  - Ejemplo: 15% → Rojo

**Cómo probar**: 
1. Modificar PER, CAGR, Div Yield para cambiar rentabilidad 5 años
2. Probar valores en cada rango
3. Modificar umbrales en Ajustes y verificar cambios

---

### 6. **VALORACIÓN 12M (%)** 📊
**Configuración**: Umbrales configurables en Ajustes (por defecto: Verde ≥10%, Amarillo ≥0%, Rojo <0%)

- [ ] **Verde**: Valoración ≥ umbral verde (por defecto ≥10%)
  - Ejemplo: 20.0% → Verde ✅ (ya probado)
- [ ] **Amarillo**: Valoración ≥ umbral amarillo pero < umbral verde (por defecto ≥0% y <10%)
  - Ejemplo: 5% → Amarillo
- [ ] **Rojo**: Valoración < umbral amarillo (por defecto <0%)
  - Ejemplo: -10% → Rojo

**Cómo probar**: 
1. Modificar PER, CAGR, Div Yield para cambiar valoración
2. Probar valores en cada rango
3. Modificar umbrales en Ajustes y verificar cambios

---

### 7. **RENTABILIDAD ANUAL (%)** 📉
**Configuración**: Umbrales configurables en Ajustes (por defecto: Verde ≥10%, Amarillo ≥0%, Rojo <0%)

- [ ] **Verde**: Rentabilidad ≥ umbral verde (por defecto ≥10%)
  - Ejemplo: 15% → Verde
- [ ] **Amarillo**: Rentabilidad ≥ umbral amarillo pero < umbral verde (por defecto ≥0% y <10%)
  - Ejemplo: 5% → Amarillo
- [ ] **Rojo**: Rentabilidad < umbral amarillo (por defecto <0%)
  - Ejemplo: -5% → Rojo

**Cómo probar**: 
1. Modificar PER, Target Price, Div Yield para cambiar rentabilidad anual
2. Probar valores en cada rango
3. Modificar umbrales en Ajustes y verificar cambios

---

### 8. **PESO EN CARTERA (%)** ⚖️
**Configuración**: Umbral máximo configurable (por defecto: 10%)
**Aplica solo a**: Assets en cartera

- [ ] **Verde**: Peso < (umbral + 10%)
  - Ejemplo: Umbral = 10%, Peso = 8% → Verde (8% < 11%)
- [ ] **Amarillo**: Peso ≥ (umbral + 10%) pero < (umbral + 25%)
  - Ejemplo: Umbral = 10%, Peso = 15% → Amarillo (15% ≥ 11% y < 12.5%)
- [ ] **Rojo**: Peso ≥ (umbral + 25%)
  - Ejemplo: Umbral = 10%, Peso = 15% → Rojo (15% ≥ 12.5%)

**Cómo probar**: 
1. Verificar assets con diferentes pesos en cartera
2. Modificar umbral máximo en Ajustes y verificar cambios
3. Probar límites exactos (umbral+10%, umbral+25%)

---

## 📝 Notas Importantes

1. **Umbrales configurables**: Todos los umbrales se pueden modificar en el botón "Ajustes" de la watchlist
2. **Recarga de página**: Después de modificar umbrales, recarga la página para ver los cambios
3. **Valores por defecto**: Si no se configuran umbrales, se usan los valores por defecto mostrados arriba
4. **Precisión**: La valoración 12M ahora se redondea a 2 decimales para evitar problemas de precisión

---

## ✅ Estado de Pruebas

- [ ] Fecha próximos resultados (3 estados)
- [ ] Indicador operativa (3 estados)
- [ ] Tier (3 estados, solo cartera)
- [ ] Cantidad a aumentar/reducir (2 estados)
- [ ] Rent. 5 años (%) (3 estados)
- [ ] Valoración 12M (%) (3 estados) - ✅ Parcialmente probado
- [ ] Rentabilidad Anual (%) (3 estados)
- [ ] Peso en cartera (%) (3 estados, solo cartera)

---

## 🔄 Orden Recomendado de Pruebas

1. **Valoración 12M (%)** - Ya probado parcialmente ✅
2. **Indicador operativa** - Fácil de probar modificando Tier
3. **Cantidad a aumentar/reducir** - Relacionado con Indicador operativa
4. **Tier** - Probado parcialmente ✅
5. **Peso en cartera** - Verificar assets con diferentes pesos
6. **Rent. 5 años (%)** - Modificar métricas manuales
7. **Rentabilidad Anual (%)** - Modificar métricas manuales
8. **Fecha próximos resultados** - Modificar fecha en edición

