# Plan de Implementación — Restructuración Portfolio + Acciones + Metales

**Versión**: 1.1  
**Fecha**: 29 Enero 2026  
**Estado**: ✅ Implementación completada (29 Enero 2026)

---

## 1. Resumen ejecutivo

### Cambios acordados

1. **Nueva pestaña "Acciones"** entre Portfolio y Cryptomonedas: solo Stock y ETF (Cartera + Watchlist + indicadores)
2. **Reorganización Portfolio**: vista global con todos los activos; mover Posiciones y Watchlist a Acciones
3. **Nueva pestaña "Metales"**: metales físicos (Oro, Plata, Platino, Paladio) con entrada manual y precios Yahoo
4. **Nuevo asset_type "Commodity"** y cuenta "Commodities" para metales

---

## 2. Estructura de navegación final

```
Portfolio (dropdown)          Acciones (dropdown)         Cryptomonedas    Metales    [Usuario]
    │                              │
    ├─ Dashboard                   ├─ Cartera
    ├─ Performance                 └─ Watchlist
    ├─ Divisas
    ├─ Transacciones
    ├─ Cuentas
    ├─ Nueva transacción
    └─ Importar CSV
```

### Orden de pestañas principales

1. Portfolio
2. Acciones
3. Cryptomonedas
4. Metales
5. Perfil de usuario

---

## 3. Detalle por módulo

### 3.1 Portfolio (dropdown)

| Enlace | Contenido | Filtro |
|--------|-----------|--------|
| Dashboard | Vista global del portfolio | Todos los activos (Stock, ETF, Crypto, Commodity) |
| Performance | Evolución, gráficos, rentabilidades | Todos |
| Divisas | Gestión de divisas | - |
| Transacciones | Lista de todas las transacciones | Todos (con filtro por tipo: Stock, ETF, Crypto, Commodity) |
| Cuentas | Gestión de cuentas/brokers | Todas |
| Nueva transacción | Formulario manual | Cualquier tipo |
| Importar CSV | Importación IBKR, DeGiro, Revolut X | - |

**Cambios respecto al estado actual:**
- Se eliminan del dropdown: Posiciones, Watchlist (pasan a Acciones)

### 3.2 Acciones (dropdown) — NUEVO

| Enlace | Contenido | Filtro |
|--------|-----------|--------|
| Cartera | Posiciones de Stock y ETF con indicadores | Solo Stock + ETF |
| Watchlist | Watchlist de activos | Solo Stock + ETF |

**Indicadores en Cartera (parte superior, solo Stock+ETF):**
1. **Dinero en Cuenta completa** — Dinero real sin apalancamiento (depósitos - retiros + P&L realizado + dividendos - comisiones)
2. **Dinero en Cartera** — Valor de posiciones incluyendo apalancamiento (valor actual de holdings)
3. **Apalancamiento/Cash** — Negativo si apalancado (broker presta), positivo si hay cash sin invertir
4. **Beneficio/Pérdida Total** — Desde el inicio, en EUR y en %

**Renombrado:** "Posiciones" → "Cartera" (solo cambio de nombre, misma vista pero filtrada)

### 3.3 Cryptomonedas

- Sin cambios en funcionalidad
- Enlace directo (no dropdown)

### 3.4 Metales — NUEVO

- Enlace directo (no dropdown)
- Dashboard con posiciones de metales físicos
- Entrada manual: compras y ventas
- Metales: Oro, Plata, Platino, Paladio (según disponibilidad en Yahoo)
- Unidad interna: gramos (oz convertida a g: 1 oz troy = 31,1035 g)
- Precios: Yahoo futuros USD (GC=F, SI=F, PL=F, PA=F) convertidos a EUR
- Botón "Actualizar precios" integrado (mismo flujo global + específico en pestaña Metales)

---

## 4. Modelo de datos

### 4.1 Asset type: Commodity

- Añadir `Commodity` a las opciones de `asset_type` (junto a Stock, ETF, Bond, Crypto)
- Metales como assets: XAU (Oro), XAG (Plata), XPT (Platino), XPD (Paladio)

### 4.2 Cuenta "Commodities"

- Broker: crear "Commodities" o "Metales físicos"
- Cuenta: "Commodities" — se crea automáticamente al registrar la primera compra manual de metales

### 4.3 Transacciones de metales

| Campo | Tipo | Notas |
|-------|------|-------|
| transaction_type | BUY / SELL | |
| asset_id | FK Asset | Asset con asset_type=Commodity |
| quantity | Float | Peso en **gramos** (siempre) |
| price | Float | Precio por gramo en EUR |
| amount | Float | Negativo en BUY, positivo en SELL |
| source | MANUAL | |
| account_id | FK | Cuenta Commodities |

### 4.4 Formulario de compra/venta metal

- Metal: Oro, Plata, Platino, Paladio
- Peso: número + unidad (oz / g)
- Precio por unidad: EUR
- Fecha
- Notas (opcional)

---

## 5. Precios Yahoo para metales

| Metal | Ticker Yahoo (futuros USD) | Conversión |
|-------|---------------------------|------------|
| Oro | GC=F | USD/oz troy → EUR/g |
| Plata | SI=F | USD/oz troy → EUR/g |
| Platino | PL=F | USD/oz troy → EUR/g |
| Paladio | PA=F | USD/oz troy → EUR/g |

- Fuente: futuros en USD por oz troy
- Conversión: tipo de cambio EUR/USD + 1 oz = 31,1035 g
- **Validación previa:** comprobar que los 4 tickers existen en Yahoo antes de implementar; si alguno falla, excluirlo

---

## 6. Filtros por asset_type

| Vista | Incluye |
|-------|---------|
| Portfolio (Dashboard, Performance, Transacciones) | Stock, ETF, Crypto, Commodity |
| Acciones (Cartera, Watchlist, indicadores) | Solo Stock, ETF |
| Cryptomonedas | Solo Crypto |
| Metales | Solo Commodity (metales físicos) |

### Filtro en Transacciones

- Añadir opción de filtro por tipo: Stock, ETF, Crypto, Commodity
- Permite ver solo transacciones de metales (u otros) si se desea

---

## 7. Plan de implementación por fases

### Fase 1: Restructuración navegación y Acciones (prioridad alta) ✅ COMPLETADA

1. ✅ Crear dropdown **Acciones** en `layout.html`
2. ✅ Crear ruta/vista **Cartera** (copia de holdings_list filtrada Stock+ETF)
3. ✅ Mover enlace Watchlist al dropdown Acciones
4. ✅ Renombrar "Posiciones" → "Cartera" en Acciones
5. ✅ Añadir indicadores en Cartera (Valor Cartera, Dinero Prestado/Cash, Dinero Usuario, B/P Total)
6. ✅ Filtrar Cartera y Watchlist: solo Stock y ETF
7. ✅ Actualizar dropdown Portfolio: quitar Posiciones y Watchlist

### Fase 2: Servicios de métricas para Acciones ✅ COMPLETADA

1. ✅ Crear `stocks_etf_metrics.py` con filtro por asset_type Stock+ETF
2. ✅ Calcular leverage, P&L total, etc. solo para Stock + ETF
3. ✅ Usar en la vista Cartera

### Fase 3: Módulo Metales — modelo y datos ✅ COMPLETADA

1. ✅ Añadir `Commodity` a asset_type
2. ✅ Crear broker y cuenta "Commodities" (seed + auto-creación en primera compra)
3. ✅ Crear assets XAU, XAG, XPT, XPD con asset_type=Commodity
4. ✅ Mapeo Yahoo: GC=F, SI=F, PL=F, PA=F
5. ✅ Validar tickers en Yahoo

### Fase 4: Módulo Metales — UI y lógica ✅ COMPLETADA

1. ✅ Crear blueprint `metales`
2. ✅ Dashboard Metales (posiciones, precios €/oz, P&L)
3. ✅ Formulario nueva compra/venta (metal, peso oz/g, precio total EUR)
4. ✅ Conversión oz → g al guardar
5. ✅ Integrar botón "Actualizar precios" en Metales
6. ✅ Añadir enlace Metales en layout
7. ✅ Crear cuenta Commodities automáticamente en primera compra

### Fase 5: Integración y filtros ✅ COMPLETADA

1. ✅ Incluir Commodity en Portfolio (Dashboard, Transacciones)
2. ✅ Añadir filtro por asset_type en Transacciones (Stock, ETF, Crypto, Commodity)
3. ✅ Metales en valor total del portfolio + fix valoración PortfolioValuation (g vs oz para Modified Dietz)

---

## 8. Validación Yahoo (preimplementación)

Antes de Fase 3, ejecutar consulta a Yahoo para verificar:
- GC=F (Oro)
- SI=F (Plata)
- PL=F (Platino)
- PA=F (Paladio)

Excluir del plan los que no devuelvan datos.

---

## 9. Resumen de decisiones cerradas

| Punto | Decisión |
|-------|----------|
| Navegación | Dropdown para Portfolio y Acciones |
| Holdings = Posiciones | Sí, mismo concepto |
| Indicadores Acciones | Dinero Cuenta, Dinero Cartera, Apalancamiento/Cash, B/P Total (%) y EUR) |
| Cartera | Solo renombrado Posiciones → Cartera, filtrado Stock+ETF |
| Transacciones metales | En Portfolio → Transacciones, con filtro Commodity |
| Cuenta metales | "Commodities", creada automáticamente |
| Unidad metales | Gramos internamente, oz y g en formulario |
| Precios metales | Futuros USD → conversión EUR |
| Ventas metales | Sí (BUY y SELL) |
| Metales incluidos | Los que existan en Yahoo (mínimo Oro y Plata) |
| Orden pestañas | Portfolio \| Acciones \| Cryptomonedas \| Metales \| Usuario |

---

## 10. Referencias

- Layout actual: `app/templates/base/layout.html`
- Métricas leverage: `app/services/metrics/basic_metrics.py` (calculate_leverage)
- Dashboard portfolio: `app/templates/portfolio/dashboard.html`
- Modelo Asset: `app/models/asset.py`
- Plan Cryptomonedas: `docs/implementaciones/CRYPTOMONEDAS_PLAN_IMPLEMENTACION.md`
