# Gemini AI / API - Documentación Oficial

Documento de referencia para la integración de **Google Gemini** en FollowUp. Centraliza modelos, configuración y funcionalidades de IA. Se actualizará conforme se añadan nuevas capacidades.

---

## 1. Resumen

La aplicación utiliza la API de **Google Gemini** para:

| Funcionalidad | Descripción |
|---------------|-------------|
| **Resumen "About the Company"** | Descripción informativa (~80-200 palabras: actividad, sector, mercados) |
| **Informes Deep Research** | Informes de inversión detallados basados en plantillas |
| **Entrega por email (opcional)** | Envío del informe completo en el cuerpo + PDF adjunto (sin resumen “Flash”) |

Todas las llamadas se realizan desde el backend. La API key nunca se expone al frontend.

---

## 2. Modelos en uso

| Uso | Variable de entorno | Modelo por defecto |
|-----|---------------------|--------------------|
| Texto (About) | `GEMINI_MODEL_FLASH` | `gemini-2.5-flash` |
| Informes Deep Research (Interactions/Agent) | `GEMINI_AGENT_DEEP_RESEARCH` | `deep-research-max-preview-04-2026` |

Las variables son opcionales. Si no se definen, se usan los valores por defecto. Permiten actualizar modelos sin cambiar código cuando Google lance nuevas versiones.

---

## 3. Configuración

### 3.1 Variables de entorno

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | Sí | Clave para la API de Gemini. La forma más directa es [Google AI Studio](https://aistudio.google.com/apikey). También puedes usar una **clave de API** creada en [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (p. ej. *FollowupAPIKey*) siempre que en ese proyecto tengas habilitada la API de **Generative Language** (o el producto que use `google-genai` en el código). Cópiala en el `.env` de la app o en variables del servicio: `GEMINI_API_KEY=...` |
| `GEMINI_MODEL_FLASH` | No | Modelo para texto. Default: `gemini-2.5-flash` |
| `GEMINI_AGENT_DEEP_RESEARCH` | No | Agente para informes Deep Research. Default: `deep-research-max-preview-04-2026` |
| `GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP` | No | 1/true (default): dos fases (plan→aprobación→informe). 0/false: **modo directo** (una fase). Reduce coste/latencia. |
| `GEMINI_DEEP_RESEARCH_MAX_WAIT_SECONDS` | No | Presupuesto máximo de polling (segundos). Default 3600; recomendado 1800 para acotar coste y evitar bloqueos silenciosos. |
| `GEMINI_DEEP_RESEARCH_MAX_CITATIONS` | No | Instrucción al agente para limitar citas (p. ej. 15). Reduce verbosidad/coste. |
| `FOLLOWUP_JOBS_WORKER_DELAY_BETWEEN_JOBS_SECONDS` | No | Delay entre jobs del worker DB-backed (throttle). Útil para control de gasto. |

No subas claves reales a Git ni a `env.example`. Si la API responde `403 PERMISSION_DENIED` con *Your API key was reported as leaked*, Google ha desactivado esa clave: crea otra en AI Studio o Cloud Console, actualiza el `.env` (local y VM) y borra o desactiva la clave antigua en la consola.

### 3.2 Dependencias

```
google-genai>=1.0.0
```

### 3.3 Comportamiento sin API key

Si `GEMINI_API_KEY` no está configurada:

- Los botones de generación de informes y audio se deshabilitan
- Se muestra mensaje informativo al usuario
 
Nota: el producto ya no genera audio/TTS. El texto anterior es histórico.

---

## 4. Arquitectura

### 4.1 Servicio principal

**`app/services/gemini_service.py`**

| Función | Modo | Descripción |
|---------|------|-------------|
| `generate_about_summary(asset)` | Síncrono | Resumen "About the Company" (párrafo detallado) |
| `run_deep_research_report(...)` | Asíncrono (poll) | Informe completo vía Interactions API |
| `generate_report_tts_audio(...)` | — | **Eliminado** (lanza error si se invoca) |

### 4.2 Rutas (API)

- `POST /portfolio/asset/<id>/about/generate` — Resumen About
- `POST /portfolio/asset/<id>/reports/generate` — Iniciar informe Deep Research
- `POST /portfolio/asset/<id>/reports/generate-and-deliver` — (Opcional) Informe + envío por correo

### 4.3 Persistencia

- **Informes**: `company_reports` (contenido Markdown, estado, telemetría de jobs y progreso JSON)
- **Resumen About**: `asset_about_summary`

---

## 5. Flujos de uso

### 5.1 Resumen About the Company

1. Usuario pulsa "Generar resumen" en Overview del asset
2. Backend valida: asset en watchlist
3. Llamada síncrona a `generate_content` con `gemini-2.5-flash` (prompt con ~80-200 palabras; `max_output_tokens` 1024; `thinking_budget=0` para que el razonamiento interno no consuma el cupo y no se corte el texto a mitad de frase)
4. Guardar en `asset_about_summary`
5. Devolver al frontend

### 5.2 Informe Deep Research

1. Usuario selecciona plantilla y pulsa "Generar informe"
2. Se crea registro en `company_reports` con `status=pending`
3. Worker DB-backed (followup-jobs) reclama la fila (cola global FIFO) y llama a Interactions API (`background=True`); se guarda `gemini_interaction_id` al crear la interacción
4. Polling hasta `completed` o `failed` (también `timeout` a las 6 h, y fallo explícito con `requires_action` o `cancelled` para no bucles infinitos)
5. Guardar contenido Markdown en BD

### 5.3 Entrega por email (todo-en-uno)

1. Usuario pulsa “Informe + correo”
2. Se encola job `full_deliver`: Deep Research → envío de email
3. El **cuerpo** del email contiene el **informe completo** y se adjunta PDF (render de HTML/CSS). No se genera resumen Flash.

---

## 6. Consideraciones

- **Rate limiting**: sin reintentos (fail-fast) en Deep Research para liberar la cola y controlar gasto
- **Seguridad**: API key solo en backend; validación de ownership antes de cada operación
- **Contenido generado**: Los informes son generados por IA; incluir aviso de que no constituyen asesoramiento financiero

---

## 7. Documentación relacionada

- **`docs/implementaciones/GEMINI_INFORMES_ESPECIFICACION.md`** — Especificación detallada de informes (plantillas, BD, API)
- **`env.example`** — Plantilla de variables de entorno

---

## 8. Próximas funcionalidades de IA

*Esta sección se ampliará a medida que se incorporen nuevas capacidades de IA.*

| Funcionalidad | Estado |
|---------------|--------|
| Resumen About the Company | ✅ Implementado |
| Informes Deep Research | ✅ Implementado |
| Audio TTS del informe | ❌ Eliminado |
| Envío de informe por correo (sin resumen Flash; cuerpo = informe completo + PDF) | ✅ Implementado |

---

*Última actualización: Mayo 2026*
