# Plan de pruebas – Portfolio (Performance + Index Comparison)

Caché HIST/NOW para `/portfolio/performance` y `/portfolio/index-comparison`, con polling cada 30s e indicadores de sincronización.

## Indicadores en UI

| Indicador | Significado |
|-----------|-------------|
| **HIST+NOW** | Reconstrucción completa del histórico (primera carga, transacción fecha pasada, cambio de día). |
| **NOW** | Solo recálculo del último punto (transacción hoy, actualización de precios). |
| **cached** | Datos servidos desde caché sin recalcular en esta petición (o caché antiguo sin tipo guardado). |
| **—** | Sin datos aún (cargando). |

**Actualizado hace X min**: se actualiza con cada poll y cada minuto en tiempo real.

---

## Prueba 1: Sanity – Carga inicial + polling activo

1. Abre en **dos pestañas**:
   - `/portfolio/performance`
   - `/portfolio/index-comparison`
2. Déjalas abiertas **sin tocar nada**.
3. Espera **al menos 60 s**.

**Resultado esperado:**

- [ ] Los gráficos/tablas cargan sin esperar demasiado.
- [ ] No se “reconstruyen” visualmente en cada ciclo si no cambia nada (la UI solo repinta cuando cambia `meta.version`).
- [ ] Los indicadores muestran HIST+NOW o NOW y “Actualizado hace X min”.

---

## Prueba 2: Transacción con fecha de hoy

1. Con ambas pestañas abiertas (performance + index-comparison).
2. En otra pestaña: crea una **nueva transacción con fecha de hoy** (depósito, compra, etc.).
3. Vuelve a las pestañas de performance e index-comparison.
4. Espera hasta **30 s** (un ciclo de polling).

**Resultado esperado:**

- [ ] Ambas pestañas se actualizan en ≤30 s sin recargar (F5).
- [ ] El indicador pasa a **NOW** (solo último punto recalculado).
- [ ] “Actualizado hace X min” se pone cercano a 0.
- [ ] Los gráficos muestran los datos correctos con la nueva transacción.

---

## Prueba 3: Transacción con fecha pasada

1. Con las pestañas abiertas.
2. Crea o edita una transacción con **fecha en el pasado** (hace semanas o meses).
3. Espera hasta **30 s** de polling.

**Resultado esperado:**

- [ ] Ambas pestañas se actualizan en ≤30 s.
- [ ] El indicador pasa a **HIST+NOW** (reconstrucción completa del histórico).
- [ ] Los gráficos reflejan correctamente el histórico con el cambio.

---

## Prueba 4: Actualización de precios

1. Con las pestañas abiertas.
2. Ve a Portfolio → actualiza precios (botón “Actualizar Precios”).
3. Espera hasta **30 s**.

**Resultado esperado:**

- [ ] Ambas pestañas se actualizan en ≤30 s.
- [ ] El indicador pasa a **NOW**.
- [ ] El último punto de los gráficos usa los nuevos precios.

---

## Prueba 5: Sin cambios (no repintar)

1. Con las pestañas cargadas y estables.
2. No hagas ninguna acción (no transacciones, no precios).
3. Espera **al menos 90 s** (3 ciclos de polling).

**Resultado esperado:**

- [ ] No hay parpadeos ni re-renders innecesarios.
- [ ] “Actualizado hace X min” sigue incrementándose cada minuto (timer en vivo).
- [ ] Los gráficos no cambian.

---

## Resumen rápido

| Prueba | Acción                    | Indicador esperado | Tiempo    |
|--------|---------------------------|--------------------|-----------|
| 1      | Carga inicial + espera 60s| HIST+NOW o NOW     | —         |
| 2      | Transacción hoy           | NOW                | ≤30 s     |
| 3      | Transacción pasada        | HIST+NOW           | ≤30 s     |
| 4      | Actualizar precios        | NOW                | ≤30 s     |
| 5      | Sin acciones 90 s         | Sin repintar       | —         |
