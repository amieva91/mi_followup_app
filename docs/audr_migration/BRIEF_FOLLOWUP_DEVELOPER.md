# Brief para agente FollowUp — cambios deseados (reforma Auðr)

**Fecha:** 16 julio 2026  
**Audiencia:** agente / desarrollador de la aplicación FollowUp (`mi_followup_app`)  
**Origen:** planning de producto Auðr (fases 0–12, backlog, ADRs)

**Contexto:** FollowUp sigue siendo la app de producción y la fuente de verdad de negocio (parsers, FIFO, fórmulas, datos). El objetivo es una **reforma integral de producto y arquitectura**, no una copia cosmética ni features de IA.

**Marca destino:** Auðr (pronunciado «Audr»; ð solo en marca/UI, no en código/URLs).

**Principio:** conservar y mejorar el núcleo financiero; rediseñar dominios, live data, UX y ops.

**Dónde se ejecuta (decisión 17 jul 2026):** en la **VM de producción actual**, con downtime indefinido aceptado. FollowUp se **congela** (backup + referencia); el código activo se escribe en el árbol **Auðr** en la misma máquina, con pasos pequeños y limpieza hasta quedar una app limpia “como desde cero”. Ver [MIGRATE_ON_PROD_VM.md](MIGRATE_ON_PROD_VM.md). **No** reescribir Flask in-place.

**F2.01 (20 jul 2026):** **No** features nuevas en FollowUp Flask; **no** `deploy-experimental` / `subidaPRO` salvo emergencia explícita (`FORCE_FOLLOWUP_DEPLOY=1`). Destino de trabajo = repo Auðr + `/var/www/audr`.

---

## Overrides activos (19 jul 2026)

**Estado:** vigentes hasta nueva decisión explícita del usuario. El resto del brief (Django/Next, dominios, SSE, admin ops, empty states, sin IA, etc.) **sigue igual**.

### A) OpenFIGI / import CSV

| Antes (brief / ADR-014 / R-03) | Ahora (override) |
|--------------------------------|------------------|
| Sin OpenFIGI automático en import | **SÍ** OpenFIGI en el flujo automático de import CSV |
| pending_admin + solo Yahoo como camino principal | **No** sustituir aún; import como FollowUp |
| R-03 “rechazado” | **No aplicar** R-03 de momento |

**Obligatorio al portar import:**

1. Comportamiento CSV **igual que FollowUp** (mismo enriquecimiento).
2. **Incluir OpenFIGI** en el flujo automático (portar/reutilizar lógica FollowUp).
3. **No** implementar todavía el modelo “pending_admin + solo Yahoo” como reemplazo del enricher.

Docs históricos “sin OpenFIGI auto” (ADR-014, ASSET_CATALOG_REDESIGN, PLANNING_MASTER) quedan **aplazados** para el criterio del import.

### B) Corporate actions / delistings (fusiones, adquisiciones, quiebras, bajas)

| Antes (rediseño Auðr) | Ahora (override) |
|-----------------------|------------------|
| Modelo `corporate_status` merged/delisted/bankrupt rediseñado como flujo principal | **No** sustituir de momento |
| Flujo nuevo inventado en Auðr | **Portar FollowUp** tal cual |

**Obligatorio:**

1. Dejar fusiones, adquisiciones, quiebras y bajas de cotización **como en FollowUp**.
2. Usar / portar `asset_delistings` con tipos **`CASH_ACQUISITION`**, **`BANKRUPTCY`** (+ reconciliación existente en FollowUp).
3. **No** inventar un flujo nuevo; **no** tomar como referencia el rediseño Auðr (`merged`/`delisted`/`bankrupt` en `catalog.Instrument.corporate_status` / `corporate_actions.py` actuales) para el port de negocio hasta nueva decisión.
4. Código Auðr ya escrito en esa línea = **DIFF a alinear con FollowUp**, no fuente de verdad.

Referencia FollowUp: `asset_delisting` + `delisting_reconciliation_service` (y callers de import/rebuild).

---

**Documentos de referencia en este repo:**

| Doc | Contenido |
|-----|-----------|
| [MIGRATE_ON_PROD_VM.md](MIGRATE_ON_PROD_VM.md) | **Playbook VM prod:** backups, dos árboles, port por capas, limpieza final |
| [PLANNING_MASTER.md](PLANNING_MASTER.md) | Roadmap producto |
| [MODULES_REDESIGN.md](MODULES_REDESIGN.md) | Dominios |
| [PRODUCT_BACKLOG.md](PRODUCT_BACKLOG.md) | Aceptado / rechazado |
| [LIVE_DATA_ARCHITECTURE.md](LIVE_DATA_ARCHITECTURE.md) | SSE |
| [CACHE_ARCHITECTURE.md](CACHE_ARCHITECTURE.md) | Caché event-driven |
| [ALERTS_ARCHITECTURE.md](ALERTS_ARCHITECTURE.md) | Alertas |
| [ASSET_CATALOG_REDESIGN.md](ASSET_CATALOG_REDESIGN.md) | Catálogo — overrides 19 jul: OpenFIGI + delistings como FollowUp |
| [EMPTY_STATES.md](EMPTY_STATES.md) | Sin datos vacíos |
| [RESPONSIVE_LAYOUT.md](RESPONSIVE_LAYOUT.md) | Móvil vs escritorio |
| [USER_PROFILE_AND_REPORTS.md](USER_PROFILE_AND_REPORTS.md) | Perfil e informes |
| [CELERY_JOBS.md](CELERY_JOBS.md) | Jobs / crons |
| [ADMIN_OBSERVABILITY.md](ADMIN_OBSERVABILITY.md) | Admin ops |

---

## 1. Decisiones cerradas (no negociar)

| Tema | Decisión |
|------|----------|
| Live data | **SSE directo** — sin fase intermedia de polling HTTP |
| Datos vacíos | **No mostrar** KPIs/gráficos/tablas sin datos reales |
| Cambio en vivo | **Flash visual** en el campo que cambió |
| Admin | **Solo operaciones** — sin pantallas de portfolio de usuario |
| Catálogo / import | **Override 19 jul:** enriquecimiento **como FollowUp**, **con OpenFIGI automático** en import. No aplicar R-03 ni “pending_admin + solo Yahoo” aún. (ADR-014 aplazado.) |
| Corporate actions / delistings | **Override 19 jul:** como FollowUp (`asset_delistings`: `CASH_ACQUISITION`, `BANKRUPTCY` + reconciliación). **No** sustituir por modelo Auðr merged/delisted/bankrupt. |
| Auth | Sin 2FA, sin OAuth social |
| IA | Sin Gemini / informes narrativos / company-report |
| Onboarding | Sin guías, popups, hitos ni “completa tu perfil” |
| Tema | MVP solo modo claro |
| Foto ticket gastos | No |
| Timeline eventos (div/splits UI) | No |
| “Salud de datos / última sync broker” | No |

---

## 2. Stack / plataforma (objetivo)

Pasar de Flask + blueprints + (SQLite/prod actual) a:

- Backend: **Django 5.2 LTS + DRF**
- Frontend: **Next.js 16 + React 19** (desacoplado vía REST)
- DB: **PostgreSQL 17** (no SQLite en prod)
- Cache/cola: **Redis 7 + Celery + Beat**
- Deploy: **Docker Compose** local y prod (Gunicorn)
- Contratos: **OpenAPI** → tipos TypeScript
- Auth: **JWT** con refresh en cookie **HttpOnly** (nunca tokens en localStorage)

Jobs > 30s → Celery. Crons actuales → Beat (ver §7).

---

## 3. Rediseño de dominios (dejar de mezclar blueprints)

Unificar los ~12 blueprints actuales en dominios claros:

| Hoy (FollowUp) | Destino |
|----------------|---------|
| `main` dashboard | **wealth** — patrimonio, metas, widgets |
| `expenses` + `incomes` | **cashflow** — un módulo, pestañas Ingresos/Gastos |
| `banks` | **banking** |
| `debts` | **liabilities** |
| `portfolio/*` | **investments** — txs, holdings, import, métricas |
| `crypto` + `metales` | **alternatives** (`asset_class=crypto\|metal`) |
| `real_estate` | **property** |
| Estrategia (solo widget) | **strategy** — pantalla propia + widget en wealth |
| `watchlist` | subdominio de **investments** |
| `asset-registry` + mappings | **catalog** (simplificado) |
| `admin` mezclado | **admin_ops** solo |
| Informes Gemini | **eliminar** |
| (nuevo) | **alerts**, **live**, **reports**, **settings/perfil** |

**Apps backend objetivo:**  
`core`, `wealth`, `cashflow`, `banking`, `liabilities`, `investments`, `alternatives`, `property`, `strategy`, `catalog`, `alerts`, `reports`, `live`, `admin_ops`.

**Navegación móvil objetivo:**

- Patrimonio → wealth (+ widget strategy)
- Finanzas → cashflow, banking, liabilities
- Inversiones → investments, alternatives, watchlist
- Más → property, alertas, ajustes, informes

---

## 4. UX / UI obligatorias

### Identidad

- Identidad visual definida **antes** de más UI de producto.
- App autenticada: Palette B clara (estilo FollowUp evolucionado).
- Sin KPIs/gráficos inventados.

### Empty states

- Si no hay datos → **no renderizar** el bloque (ni `0,00 €` engañoso, ni CTA de onboarding).
- Componente tipo `AudrEmptyGuard`.

### Live

- Un canal SSE por usuario.
- Payload con `changed_fields[]`.
- Flash visual solo en esos campos.

### Responsive (dos UIs, no “el mismo HTML más estrecho”)

- Breakpoint **1024px**.
- **Móvil:** resumen mínimo (consulta rápida).
- **Escritorio:** tablas, historial, herramientas.
- Vistas separadas Mobile/Desktop; misma API.
- Nav: bottom nav (móvil) / sidebar (escritorio).
- Admin: **solo escritorio**.

### Features UX aceptadas

- Entrada rápida gasto/ingreso (móvil)
- Simulador amortización deuda inline
- Feed “qué cambió” en patrimonio
- Búsqueda global Cmd+K
- Pantalla estrategia dedicada
- PWA instalable (fase ops)
- Web Push alertas (fase ops)

---

## 5. Capas transversales a implementar

### 5.1 Live (SSE)

- Snapshot REST + stream SSE desde el día 1 de la nueva base.
- Dominios publican eventos; UI se actualiza sin refresh.
- Reconexión con backoff + re-snapshot.

### 5.2 Caché

- Caché **event-driven** (no solo por tiempo).
- Full vs incremental; alcance **día o mes** según dominio.
- Triggers: import, CRUD usuario, validación admin de instrumento, jobs de mercado.

### 5.3 Alertas (dominio desacoplado)

- `AlertRule` + `AlertDelivery` en BD (activar/desactivar sin deploy).
- Solo **lectura** de métricas normalizadas (`metric_id`); sin imports circulares desde investments/wealth.
- Canales MVP: **in-app + email**; push después.
- Cooldown por regla; feature flag para apagar el evaluador.

**Tipos de alerta a soportar:**

- Patrimonio / meta (`net_worth_eur`, progreso meta)
- Total bolsa / posición / P/L %
- Crypto y metales
- Watchlist precio
- Banda estrategia SG
- Gastos mes vs media
- Cuota deuda próxima
- Ops admin (APIs, workers)

### 5.4 Catálogo, import y corporate actions (overrides 19 jul 2026)

**Import CSV (vigente):**

- Portar/reutilizar la lógica de **enriquecimiento de FollowUp**, **incluyendo OpenFIGI** en el flujo automático.
- Mismo resultado observable que FollowUp al importar (mappings, ticker, metadatos vía enricher).
- **No** sustituir aún por “instrumento `pending_admin` + solo Yahoo”.

**Corporate actions / delistings (vigente):**

- Fusiones, adquisiciones, quiebras y bajas de cotización: **igual que FollowUp**.
- Portar `asset_delistings` (`CASH_ACQUISITION`, `BANKRUPTCY`, …) + **reconciliación existente** FollowUp.
- **No** inventar flujo nuevo; **no** usar como verdad el rediseño Auðr `corporate_status` merged/delisted/bankrupt.

**Dirección de producto aplazada (ADR-014 / ASSET_CATALOG_REDESIGN — no usar para el port actual):**

- Instrumento curado admin + Yahoo; cola `pending_admin`.
- Admin valida → rebuild holdings sin reimportar CSV.
- Modelo corporate_status rediseñado en Auðr.

Cuando el usuario reactive ADR-014 / rediseño delistings, se documentará el cutover.

### 5.5 Perfil

- Cuenta: display name, email, cambio contraseña.
- Preferencias: timezone (`Europe/Madrid`), moneda base EUR, locale `es-ES`.
- Toggle email de alertas.
- **No** avatar, 2FA, OAuth, dark mode, wizard de perfil.

### 5.6 Informes (datos, no IA)

- PDF/CSV: patrimonio, cartera, cashflow.
- Generación async + progreso (SSE).
- Distinto del “export backup técnico” GDPR.

### 5.7 Admin ops

- Rutas `/admin/*` separadas; usuario normal no las ve.
- Monitor live (SSE ops): workers, Beat, errores API.
- Diagrama de arquitectura live (nodos/conexiones; logs al click).
- Validación de catálogo pendiente.

---

## 6. Dominios de producto — cambios funcionales

### Wealth

- Dashboard patrimonio unificado + metas.
- Widgets desde otros dominios.
- Feed de cambios recientes.

### Cashflow

- Ingresos + gastos juntos.
- Entrada rápida móvil.
- Categorías; consumo de dividendos/fees de extractos donde aplique.

### Banking / Liabilities

- Saldos bancarios.
- Deudas + simulador amortización.
- Alertas de cuota próxima.

### Investments (núcleo a conservar y endurecer)

- **Portar** parsers IBKR/DeGiro, FIFO, fórmulas (con tests).
- Import multi-archivo (IBKR + DeGiro txs + DeGiro account).
- Holdings materializados; P/L realizado; corporate actions.
- Watchlist; performance (p. ej. Modified Dietz).
- Price poll Yahoo rotativo (mantener en Beat).

### Alternatives

- Crypto + metales en patrimonio.
- **Nuevo:** import **Revolut X** (CSV crypto) — no existe hoy en FollowUp.

### Property / Strategy

- Inmuebles.
- Estrategia SG: pantalla propia + scores/bandas alertables; job macro diario.

### Reports / Settings

- Ver §5.5 y §5.6.

---

## 7. Jobs (crons actuales → Beat)

| Job FollowUp | Acción |
|--------------|--------|
| Price poll | KEEP |
| Cache rebuild | KEEP (event-driven + worker) |
| Benchmark global | KEEP |
| Global strategy macro | KEEP |
| Euribor / interest context | KEEP si hay hipotecas |
| Analyst consensus | OPCIONAL (solo si watchlist lo usa) |
| Company-report / Gemini queues | **DROP** |

**Nuevos:**

- Evaluar alertas (p. ej. cada 5 min)
- Publicar métricas ops admin
- Cleanup caché expirada

---

## 8. Variables / calidad de código

- Nombres de métricas explícitos: `net_worth_eur`, `position_unrealized_pl_pct`, `sg_global_score`, etc.
- Servicios < ~400 LOC.
- Portar math con tests; **revisar fórmulas al inicio de cada dominio**.
- Sin onboarding ni placeholders educativos.

---

## 9. Orden de trabajo sugerido (producto)

1. Identidad visual + empty + flash
2. Contratos API/SSE
3. Fundación (Docker/Django/Next/Celery/SSE/auth/perfil API)
4. Live shell (nav + snapshot real)
5. Investments + catálogo Yahoo
6. Cashflow + banking + liabilities
7. Wealth + alertas + UI perfil
8. Alternatives (+ Revolut X) + property + strategy
9. Admin ops + PWA/push
10. Migración datos + export backup + informes
11. Deploy/DNS cutover

*(La migración de datos puede ir en paralelo por dominio; no dejarla solo al final si se puede.)*

---

## 10. Fuera de alcance / diferido

- Spending plan completo
- Macro inflación por país
- Plan pensiones
- Open Banking
- Modo offline
- Informes programados por email

→ post-MVP / fases 12+.

---

## 11. Qué NO cambiar (conservar)

- Lógica de negocio validada: parsers brokers, FIFO, corporate actions / delistings **como FollowUp** (`asset_delistings` + reconciliación; override 19 jul), fórmulas de patrimonio/performance.
- Datos de prod enriquecidos (`asset_registry`, delistings, mappings) — migrar, no re-enriquecer a ciegas.
- FollowUp en prod (IP / dominio) sigue de referencia hasta paridad y cutover.

---

## 12. Criterio de “hecho” por dominio

- API + UI móvil/escritorio según matriz dual
- SSE/caché si el dominio emite cambios
- Fórmulas revisadas + tests
- Sin gráficos vacíos
- Métricas expuestas a alertas si aplica
- Admin ops no mezcla vistas de usuario

---

## Prompt corto para el agente FollowUp

```
Lee docs/BRIEF_FOLLOWUP_DEVELOPER.md en el repo Auðr (o el fichero que te pase el usuario).
Implementa / planifica según ese brief: reforma de producto y arquitectura hacia Auðr,
conservando parsers/FIFO/fórmulas y datos enriquecidos de FollowUp.
Respeta las decisiones cerradas (§1) y el orden sugerido (§9).
No añadas IA, 2FA, OAuth ni onboarding.
OpenFIGI: SÍ en import automático (override 19 jul) — portar lógica FollowUp; no aplicar R-03.
Corporate actions/delistings: como FollowUp (asset_delistings CASH_ACQUISITION/BANKRUPTCY + reconciliación); no modelo Auðr merged/delisted/bankrupt aún.
```
