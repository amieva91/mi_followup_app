## Estado actual (Mayo 2026): Informes Gemini (Deep Research) en FollowUp

Este documento resume **cómo están hoy los informes**, qué se cambió respecto al diseño inicial y **por qué**, para poder retomar pruebas el mes que viene con contexto.

### Objetivo principal

- **Reducir coste** y evitar “colas bloqueadas” manteniendo el valor del informe para el usuario.
- Mantener una UX clara: **DR (informe)** y, opcionalmente, **DR + email**.

---

## 1) Flujos vigentes

### 1.1 Deep Research (solo informe)

- **Qué hace**: Genera el informe con **Deep Research (Interactions API)** y lo guarda en `company_reports.content`.
- **Resultado**: visible en la UI; no hay resumen aparte ni audio.

### 1.2 Todo-en-uno (informe + email)

- **Qué hace**: ejecuta **DR → envío de email**.
- **Email**:
  - **Cuerpo**: contiene el **informe completo** (Markdown).
  - **Adjunto**: **PDF** generado (Playwright/Chromium) a partir del informe.
- **Nota**: no se genera resumen “Flash” previo al email.

---

## 2) Cambios clave y justificación

### 2.1 Eliminación definitiva de audio/TTS

- **Antes**: guion + TTS + WAV, botones de UI, endpoints de audio, adjunto WAV en emails.
- **Ahora**: audio eliminado por coste y complejidad operativa.
- **Motivo**: el audio llegó a concentrar la mayor parte del gasto diario y añadía puntos frágiles (timeouts, ficheros, reintentos, colas separadas).

### 2.2 “Resumen Flash” eliminado

- **Antes**: se generaba un resumen (modelo Flash) para el cuerpo del email.
- **Ahora**: el email usa directamente el **informe completo**.
- **Motivo**: reducir llamadas extra (coste) y evitar inconsistencias (resumen vs informe).

### 2.3 Progreso unificado: `job_progress_json`

- **Antes**: `audio_progress_json` se usaba como progreso (aunque ya no fuese solo audio).
- **Ahora**: campo neutro `job_progress_json` en `company_reports`.
- **Compatibilidad UI**: la API sigue devolviendo la clave `audio_progress` por compatibilidad, pero su contenido viene de `job_progress_json`.
- **Motivo**: eliminar deuda técnica: “audio_*” ya no representa la realidad del sistema.

### 2.4 Control de coste / “fail-fast”

Aplicado a Deep Research para controlar gasto y no bloquear la cola:

- **Sin reintentos** (una sola tentativa por operación).
- **Máximo de espera** (polling) configurable.
- **Límite blando de citas/fuentes** (instrucción al agente) para reducir verbosidad.
- **Throttle** del worker entre jobs (delay configurable).

---

## 3) Variables de entorno relevantes (coste)

- `GEMINI_AGENT_DEEP_RESEARCH`
  - agente Deep Research usado por `interactions.create`.
- `GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP`
  - `1`: 2 fases (plan→aprobación→informe).
  - `0`: **modo directo** (1 fase). Menor coste/latencia.
- `GEMINI_DEEP_RESEARCH_MAX_WAIT_SECONDS`
  - presupuesto máximo de polling.
- `GEMINI_DEEP_RESEARCH_MAX_CITATIONS`
  - límite blando de citas.
- `FOLLOWUP_JOBS_WORKER_DELAY_BETWEEN_JOBS_SECONDS`
  - delay entre jobs del worker (throttle).

---

## 4) Qué mirar cuando vuelvan los créditos (checklist)

### 4.1 Prueba 1 — Deep Research desde watchlist

- Iniciar un informe desde watchlist.
- Verificar:
  - Se completa o falla con mensaje claro.
  - La UI muestra progreso (vía `job_progress_json`).
  - La cola no se bloquea si falla.

### 4.2 Prueba 2 — Todo-en-uno (informe + email)

- Iniciar “Informe + correo”.
- Verificar:
  - El email llega.
  - **Cuerpo** contiene el informe completo.
  - **PDF adjunto** correcto.
  - `email_status` y `delivery_phase_status` coherentes.

### 4.3 Prueba 3 — Control de coste

- Lanzar 2 informes seguidos.
- Verificar:
  - se respeta el **delay** entre jobs del worker,
  - no hay reintentos,
  - el tiempo máximo de espera corta correctamente si hay bloqueo.

---

## 5) Referencias en el repo

- `GEMINI_IA.md` (doc oficial de integración)
- `app/services/gemini_service.py` (Interactions/Deep Research + prompts + límites)
- `app/services/company_report_jobs_worker.py` (worker DB-backed + throttle)
- `app/services/full_deliver_continuation.py` (cola DR→email)
- Migración: `migrations/versions/jobprogress01_remove_audio_columns_and_rename_progress_json.py`

