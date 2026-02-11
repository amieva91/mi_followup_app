# Plan de pruebas — Módulo Cryptomonedas

**Fecha**: 29 Enero 2026  
**Módulo**: Cryptomonedas (Revolut X)  
**Versión**: 1.0

---

## 1. Prerequisitos

- [x] Servidor FollowUp en ejecución (`python run.py`)
- [x] Usuario registrado y logueado
- [x] Archivo CSV de prueba: `revx-account-statement_2018-10-18_2026-02-08_es-es_1442ce.csv` en uploads/

---

## 2. Pruebas de navegación

| # | Acción | Resultado esperado | Estado |
|---|--------|--------------------|--------|
| 2.1 | Ir a la barra de navegación | Se muestra el enlace **🪙 Cryptomonedas** entre Portfolio y el nombre de usuario | [x] OK |
| 2.2 | Clic en **Cryptomonedas** | Se carga la ruta `/crypto` y el dashboard de cryptomonedas | [x] OK |
| 2.3 | Sin datos importados | Se muestra el estado vacío con mensaje "Sin posiciones en cryptomonedas" y botón "Importar CSV Revolut X" | N/A (datos ya importados) |

---

## 3. Pruebas de importación CSV

| # | Acción | Resultado esperado | Estado |
|---|--------|--------------------|--------|
| 3.1 | Ir a **Portfolio → Importar CSV** | Se carga el formulario de subida de CSV | [x] OK |
| 3.2 | Seleccionar archivo `revx-account-statement_*.csv` | El archivo se selecciona correctamente | [x] OK |
| 3.3 | Subir el archivo | Se detecta formato **REVOLUT_X** automáticamente | [x] OK |
| 3.4 | Tras la importación | Se crea broker "Revolut" si no existía | [x] OK |
| 3.5 | Tras la importación | Se crea cuenta "Revolut Crypto" si no existía | [x] OK |
| 3.6 | Tras la importación | Aparece mensaje de éxito con estadísticas (transacciones, holdings, assets) | [x] OK |
| 3.7 | Subir el mismo archivo de nuevo | No se duplican transacciones (detección de duplicados) | [x] OK (0 transacciones importadas, 3 posiciones) |

---

## 4. Pruebas del dashboard Cryptomonedas

| # | Acción | Resultado esperado | Estado |
|---|--------|--------------------|--------|
| 4.1 | Tras importar CSV, ir a **Cryptomonedas** | Se muestran las métricas principales | [x] OK |
| 4.2 | Verificar tarjeta **Capital invertido** | Valor > 0 en EUR (suma de costes de holdings) | [x] OK |
| 4.3 | Verificar tarjeta **Cuasi-fiat** | Valor en EUR si hay USDT u otras stablecoins | [x] OK |
| 4.4 | Verificar tarjeta **Valor actual** | Suma de (cantidad × precio actual) por activo | [x] OK |
| 4.5 | Verificar tarjeta **P&L Total** | Valor y % coherentes con valor actual - capital | [x] OK |
| 4.6 | Verificar sección **Fiat total** | Desglose: capital + cuasi-fiat | [x] OK |
| 4.7 | Verificar sección **Rewards** | Valor estimado si hay staking rewards (ADA, etc.) | [x] OK |
| 4.8 | Verificar tabla **Posiciones** | Columnas: Activo, Cantidad, Precio medio, Precio, Coste, Valor, P&L, Rewards | [x] OK |
| 4.9 | Si hay ADA con staking | Columna Rewards muestra valor estimado | [x] OK |

---

## 5. Pruebas de precios Yahoo

| # | Acción | Resultado esperado | Estado |
|---|--------|--------------------|--------|
| 5.1 | Ir a **Portfolio → Actualizar Precios** | Se ejecuta la actualización de precios | [x] OK |
| 5.2 | Tras actualizar, volver a **Cryptomonedas** | Valores actualizados (Valor actual, P&L) | [x] OK |
| 5.3 | Verificar precios | Assets crypto (ADA, ETH, etc.) tienen precios en EUR | [x] OK |

---

## 6. Pruebas de integración con Portfolio

| # | Acción | Resultado esperado | Estado |
|---|--------|--------------------|--------|
| 6.1 | Ir a **Portfolio → Dashboard** | Las posiciones crypto aparecen en el portfolio unificado | [x] OK |
| 6.2 | Ir a **Portfolio → Posiciones** | Se listan holdings de Revolut Crypto | [x] OK |
| 6.3 | Ir a **Portfolio → Transacciones** | Se listan las transacciones importadas (Buy, Sell, rewards como Buy a 0) | [x] OK |

---

## 7. Pruebas de consistencia

| # | Verificación | Criterio |
|---|--------------|----------|
| 7.1 | Capital invertido | ≈ suma de costes de compras (incluyendo fees) |
| 7.2 | Rewards | Cantidad de ADA (u otro) de staking ≈ suma de rewards en tabla |
| 7.3 | P&L por activo | (Valor - Coste) / Coste × 100 ≈ % mostrado |
| 7.4 | Sin errores en consola | No hay tracebacks ni errores 500 |

---

## 8. Pruebas de errores y bordes

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 8.1 | Subir CSV que no sea Revolut X | Se detecta como UNKNOWN o otro formato; mensaje apropiado |
| 8.2 | Subir archivo vacío o corrupto | Mensaje de error claro, no falla el servidor |
| 8.3 | Acceder a `/crypto` sin sesión | Redirige a login |

---

## 9. Checklist rápido

```
[x] Navegación: enlace Cryptomonedas visible
[x] Import: subir revx CSV → éxito
[x] Dashboard: métricas y tabla de posiciones (incl. Precio medio)
[x] Rewards: se muestran si hay staking
[x] Actualizar precios: funciona desde Portfolio
[x] Integración: crypto visible en Portfolio
[x] Duplicados: no se repiten transacciones
```

---

## 10. Guía de obtención CSV Revolut X

En la página **Portfolio → Importar CSV** hay una guía completa. Resumen:
1. Acceder a [exchange.revolut.com](https://exchange.revolut.com/) e iniciar sesión
2. Clic en perfil de usuario (arriba derecha) → **Documentos y extractos**
3. Seleccionar **Extracto de cuenta** → Formato **CSV** → Período **Desde el principio** → **Generar**

---

## 11. Archivo de prueba sugerido

Usar el CSV de ejemplo:
- `revx-account-statement_2018-10-18_2026-02-08_es-es_1442ce.csv` (en uploads/)

Contiene:
- Buys/Sells de XRP, ETH, BTC, ADA
- Staking rewards de ADA
- Operaciones con USDT (Receive/Sell)
