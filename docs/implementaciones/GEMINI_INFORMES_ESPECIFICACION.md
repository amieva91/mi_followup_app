# Especificación: Integración Gemini para Informes de Compañías

**Documento de especificación técnica**  
**Fecha:** 29 de enero de 2026  
**Estado:** Implementado (con extensiones Email + TTS)  
**Última actualización:** 6 Febrero 2026

---

## 1. Resumen ejecutivo

Integración de la API de Google Gemini en la aplicación para generar:

1. **Informes de investigación (Deep Research)**: Informes detallados sobre compañías, basados en una descripción y puntos opcionales definidos por el usuario. Se ejecutan en segundo plano (varios minutos) y se guardan hasta un máximo de 5 por asset.

2. **Resumen "About the Company"**: Descripción corta (pocas líneas) de qué hace la compañía. Generación rápida (una sola llamada), almacenada de forma permanente hasta que el usuario la sobrescriba o borre el asset de la watchlist.

**Alcance:** Solo assets que aparecen en la watchlist del usuario (ya sea en cartera o solo en seguimiento). No aplica a assets que no están en watchlist.

---

## 2. APIs de Gemini utilizadas

### 2.1 Informe completo (Deep Research)

- **API:** API de Interactions (no `generate_content`).
- **Referencia:** [Gemini Deep Research - Documentación oficial](https://ai.google.dev/gemini-api/docs/deep-research?hl=es-419)
- **Agente:** `deep-research-max-preview-04-2026` (variante Max, máxima exhaustividad)
- **Modo:** Ejecución en segundo plano obligatoria (`background=True`).
- **Flujo:**
  1. `client.interactions.create(input=..., agent='deep-research-max-preview-04-2026', background=True)` → devuelve `interaction.id`
  2. Poll con `client.interactions.get(interaction.id)` hasta `status == "completed"` o `"failed"`
  3. El resultado final está en `interaction.outputs[-1].text`
- **Duración típica:** Varios minutos (hasta ~20–60 min).
- **Formato recomendado para el informe:** Markdown (se puede pedir en el prompt). El frontend renderizará Markdown a HTML para visualización.
- **Coste estimado:** ~2–5 USD por tarea según profundidad.

### 2.2 Resumen "About the Company"

- **API:** `generate_content` (API estándar de Gemini).
- **Modelo sugerido:** `gemini-2.5-flash` (respuesta rápida); alternativas según la doc de Google.
- **Modo:** Llamada síncrona única.
- **Duración típica:** Segundos.
- **Contexto del prompt:** Nombre, símbolo e ISIN del asset en la base de datos. No hay contexto extra introducido por el usuario.

---

## 3. Base de datos

### 3.1 Nueva tabla: `report_settings`

Almacena la plantilla de investigación por usuario (descripción + puntos/preguntas).

| Campo       | Tipo       | Descripción                                                                 |
|------------|------------|-----------------------------------------------------------------------------|
| id         | INTEGER    | Primary key                                                                 |
| user_id    | INTEGER    | FK a users.id, UNIQUE. Un registro por usuario.                            |
| description| TEXT       | Descripción de la investigación. **Obligatorio** para poder generar informes. |
| points     | TEXT       | JSON array de strings. Puntos/preguntas opcionales. Ej: `["Punto 1", "Punto 2"]` |
| created_at | DATETIME   |                                                                             |
| updated_at | DATETIME   |                                                                             |

- **Constraint:** Un usuario solo tiene un registro (user_id único).
- **Validación:** Para habilitar el botón "Generar informe", `description` no debe estar vacío.

### 3.2 Nueva tabla: `company_reports`

Informes de Deep Research generados.

| Campo        | Tipo     | Descripción                                                                 |
|-------------|----------|-----------------------------------------------------------------------------|
| id          | INTEGER  | Primary key                                                                 |
| user_id     | INTEGER  | FK a users.id                                                               |
| asset_id    | INTEGER  | FK a assets.id                                                              |
| content     | TEXT     | Contenido del informe (Markdown o HTML según decisión final)                |
| status      | VARCHAR  | `pending`, `processing`, `completed`, `failed`                               |
| error_msg   | TEXT     | Mensaje de error si status = `failed`                                       |
| gemini_interaction_id | VARCHAR | ID de la interacción Gemini para reanudar/poll si aplica           |
| audio_path | VARCHAR | Ruta al archivo WAV (ej: `reports_audio/report_123.wav`)            |
| audio_status | VARCHAR | `pending`, `processing`, `completed`, `failed`                      |
| audio_error_msg | TEXT | Mensaje de error si audio_status = failed                           |
| audio_completed_at | DATETIME | Fecha de finalización del audio                                     |
| created_at  | DATETIME | Fecha de solicitud                                                          |
| completed_at| DATETIME | Fecha de finalización (cuando status pasa a completed/failed)               |

- **Regla de retención:** Máximo 5 informes por (user_id, asset_id). Al generar el 6º, se borra el más antiguo (`ORDER BY created_at ASC LIMIT 1` antes de insertar).
- **Borrado en cascada:** Si el asset se elimina de la watchlist del usuario, se borran **todos** los informes de ese (user_id, asset_id).

### 3.3 Nueva tabla o campo: Resumen "About the Company"

**Opción A – Campo en Asset:**  
Añadir `about_summary` (TEXT) y `about_summary_user_id` (INTEGER, FK users) en `assets`. Problema: los assets son globales; varios usuarios podrían tener el mismo asset. No aplica bien.

**Opción B – Tabla `asset_about_summary`:**  
Almacenar por usuario y asset.

| Campo           | Tipo     | Descripción                                                |
|----------------|----------|------------------------------------------------------------|
| id             | INTEGER  | Primary key                                                |
| user_id        | INTEGER  | FK a users.id                                              |
| asset_id       | INTEGER  | FK a assets.id                                             |
| summary        | TEXT     | Resumen generado (texto plano o Markdown corto)            |
| created_at     | DATETIME |                                                            |
| updated_at     | DATETIME |                                                            |

- **Constraint:** UNIQUE(user_id, asset_id). Un registro por usuario y asset.
- **Comportamiento:** Al generar de nuevo, se hace UPDATE del registro existente (sobrescribe). Al borrar el asset de la watchlist, se borra este registro.

### 3.4 Índices recomendados

- `company_reports`: (user_id, asset_id), (status), (created_at)
- `asset_about_summary`: (user_id, asset_id) único
- `report_settings`: user_id único

---

## 4. Modelo de dominio y reglas de negocio

### 4.1 Alcance de assets

- Solo assets que aparecen en la watchlist del usuario.
- Incluye:
  - Assets en cartera (con posición).
  - Assets en seguimiento (watchlist) sin posición.
- Excluye: cualquier asset que no esté en watchlist.

### 4.2 Plantilla de informe (report_settings)

- **Por usuario:** Cada usuario tiene su propia plantilla (descripción + puntos).
- **Descripción:** Obligatoria. Si está vacía, el botón "Generar informe" debe estar **deshabilitado**.
- **Puntos/preguntas:** Opcionales. Lista dinámica con botón "+" para añadir más.
- **Plantilla global:** La misma plantilla se usa para todos los assets al generar informes; no hay plantilla por asset.

### 4.3 Informes (company_reports)

- **Máximo 5 por asset y usuario.** Al generar el 6º, se elimina el más antiguo.
- **Si el asset se borra de la watchlist:** Se eliminan todos los informes de ese asset para ese usuario.
- **Generación en segundo plano:** Tras pulsar "Generar informe", la tarea corre en background. Cuando termine, se guarda en BD aunque el usuario no esté en la pestaña. El informe aparecerá en la ruta correspondiente cuando el usuario acceda.
- **Estados:** `pending` → `processing` → `completed` o `failed`.

### 4.4 Resumen "About the Company"

- **Almacenamiento:** Permanente hasta que el usuario borre el asset de la watchlist o vuelva a pulsar "Generar resumen" (en ese caso se sobrescribe).
- **Contexto:** Siempre nombre, símbolo e ISIN del asset en BD. Sin contexto extra del usuario.
- **API:** Llamada rápida con `generate_content`, no Deep Research.

---

## 5. Interfaz de usuario (UI)

### 5.1 Página Asset Detail (`/portfolio/asset/<id>`)

La ruta actual ya restringe el acceso a assets en cartera o watchlist.

#### 5.1.1 Renombrar tab "📊 Métricas de Mercado" → "Overview"

- El contenido actual (País, Sector, Industria) se mantiene.
- **Eliminar** de esta tab: "Precio Anterior" y "Cambio del Día".
- **Añadir** sección "About the Company":
  - Si hay resumen guardado: mostrarlo.
  - Botón "Generar resumen": llama a la API rápida. Si ya existe, al pulsar se sobrescribe.
  - Estado de carga mientras se genera.

#### 5.1.2 Nueva tab "Informes" (junto a Transacciones)

- Orden sugerido de tabs: Overview, Valoración, Riesgo y Dividendos, Análisis, **Informes**, Transacciones.
- Contenido:
  - Listado de informes (hasta 5) ordenados por fecha descendente (más reciente primero).
  - Cada informe: fecha de creación, fecha de actualización/completado, enlace o vista expandida al contenido.
  - Botón "Generar informe": inicia la generación (en segundo plano). Habilitado solo si existe descripción guardada en ajustes.
  - Indicador de estado si hay un informe en curso (`processing` o `pending`).
  - Al seleccionar un informe, se muestra el contenido renderizado (Markdown → HTML).

#### 5.1.3 Botón "Ajustes" (informes)

- Ubicación: En la página de detalle del asset (por ejemplo, en el header o cerca de "Generar informe").
- Abre un modal o sección donde el usuario define:
  - **Descripción de la investigación** (obligatorio): texto libre.
  - **Puntos/preguntas** (opcional): lista con botón "+" para añadir ítems. Cada ítem es un campo de texto.
- Guardar: persiste en `report_settings` para ese usuario. Esta plantilla se usa para todos los assets al generar informes.
- Validación: La descripción no puede estar vacía para poder guardar y habilitar "Generar informe".

### 5.2 Watchlist (`/portfolio/watchlist`)

#### 5.2.1 Columna "ACCIONES"

- Añadir un botón "Generar informe" (o icono tipo 📄) junto a Editar y Eliminar.
- **Condición:** El botón está **deshabilitado** si el usuario no tiene descripción guardada en `report_settings`.
- Si está habilitado: al pulsar, inicia la generación del informe para ese asset en segundo plano. El usuario puede seguir navegando; el informe se guardará cuando Gemini termine.
- Comportamiento opcional: mostrar tooltip "Define la descripción en Ajustes del asset para habilitar" cuando esté deshabilitado.

### 5.3 Tres botones de generación (resumen)

| Ubicación                     | Botón                 | Acción                                                       |
|------------------------------|------------------------|--------------------------------------------------------------|
| Asset detail – Overview      | "Generar resumen"      | Genera resumen "About the Company" (API rápida)              |
| Asset detail – Tab Informes  | "Generar informe"      | Genera informe completo (Deep Research)                      |
| Watchlist – Columna ACCIONES | "Generar informe" (📄) | Genera informe completo (Deep Research) para ese asset       |

---

## 6. Flujos técnicos

### 6.1 Generación de informe (Deep Research)

1. Usuario pulsa "Generar informe" (desde asset detail o watchlist).
2. Backend valida:
   - Asset en watchlist (o cartera).
   - `report_settings` del usuario con `description` no vacía.
3. Backend crea registro en `company_reports` con `status=pending`.
4. Se lanza un hilo o tarea en background que:
   - Actualiza `status=processing`.
   - Construye el `input` para Gemini: descripción + puntos (si existen) + contexto del asset (nombre, símbolo, ISIN).
   - Llama a `client.interactions.create(..., background=True)`.
   - Guarda `gemini_interaction_id`.
   - Entra en bucle de poll cada N segundos hasta `completed` o `failed`.
   - Si `completed`: guarda `content`, `status=completed`, `completed_at`.
   - Si `failed`: guarda `error_msg`, `status=failed`.
5. Antes de insertar el nuevo informe, si ya hay 5 informes para (user_id, asset_id), se elimina el más antiguo.
6. El frontend puede ofrecer un endpoint de estado (por ejemplo `GET /api/reports/<report_id>/status`) para mostrar progreso.

### 6.2 Generación de resumen "About the Company"

1. Usuario pulsa "Generar resumen" en Overview.
2. Backend valida: asset en watchlist.
3. Prompt a Gemini: "En 3–5 líneas, describe qué hace la empresa [nombre], símbolo [símbolo], ISIN [isin]. Respuesta concisa en español."
4. Llamada síncrona a `generate_content`.
5. Guardar o actualizar en `asset_about_summary` (INSERT o UPDATE según exista registro).
6. Devolver el resumen al frontend para mostrarlo de inmediato.

### 6.3 Borrado en cascada

- **Al eliminar un asset de la watchlist:**
  - Borrar todos los registros de `company_reports` con ese (user_id, asset_id).
  - Borrar el registro de `asset_about_summary` para ese (user_id, asset_id).

Esto debe ejecutarse en la lógica que elimina ítems de la watchlist (por ejemplo, en el handler de `deleteWatchlistItem` o equivalente).

---

## 7. API REST / Endpoints

### 7.1 Report Settings

| Método | Ruta                         | Descripción                                        |
|--------|------------------------------|----------------------------------------------------|
| GET    | `/portfolio/api/report-settings` | Obtener plantilla del usuario (description, points) |
| POST   | `/portfolio/api/report-settings` | Guardar plantilla (description, points)             |

### 7.2 Informes

| Método | Ruta                                      | Descripción                                                |
|--------|-------------------------------------------|------------------------------------------------------------|
| POST   | `/portfolio/asset/<id>/reports/generate`  | Iniciar generación de informe (Deep Research)              |
| GET    | `/portfolio/asset/<id>/reports`           | Listar informes del asset (hasta 5)                        |
| GET    | `/portfolio/asset/<id>/reports/<report_id>` | Obtener un informe concreto (para vista detalle)         |
| GET    | `/portfolio/api/reports/<report_id>/status` | Estado de un informe (pending/processing/completed/failed) |

### 7.3 Resumen "About the Company"

| Método | Ruta                                    | Descripción                              |
|--------|-----------------------------------------|------------------------------------------|
| POST   | `/portfolio/asset/<id>/about/generate`  | Generar resumen (API rápida)             |
| GET    | `/portfolio/asset/<id>/about`           | Obtener resumen guardado (si existe)     |

### 7.4 Envío por correo (implementado Ene 2026)

| Método | Ruta                                                | Descripción                                      |
|--------|-----------------------------------------------------|--------------------------------------------------|
| POST   | `/portfolio/asset/<id>/reports/<report_id>/send-email` | Enviar informe al email registrado del usuario   |

- Requiere: `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD` (Gmail: Contraseña de aplicación).
- Contenido Markdown convertido a HTML. `app/utils/email.py` → `send_report_email()`.
- **Audio adjunto**: Si el informe tiene audio TTS generado (`audio_status=completed`), se adjunta automáticamente el archivo WAV al correo. Si no existe, solo se envía el informe en texto.

### 7.5 Audio TTS (implementado Ene 2026)

| Método | Ruta                                                    | Descripción                                      |
|--------|---------------------------------------------------------|--------------------------------------------------|
| POST   | `/portfolio/asset/<id>/reports/<report_id>/generate-audio` | Iniciar generación de audio TTS en background    |
| GET    | `/portfolio/asset/<id>/reports/<report_id>/audio`       | Descargar archivo WAV del audio                  |

- Nuevos campos en `company_reports`: `audio_path`, `audio_status`, `audio_error_msg`, `audio_completed_at`.
- Servicio: `app/services/gemini_service.py` → `generate_report_tts_audio()`.
- Flujo: 1) Resumen corto con gemini-2.5-flash; 2) TTS con gemini-3.1-flash-tts-preview; 3) Guardar WAV en `output/reports_audio/`.

---

## 8. Dependencias y configuración

### 8.1 Nuevas dependencias Python

- `google-genai` (SDK oficial de Gemini para Python) o equivalente según documentación actual.
- Verificar versión compatible con la API de Interactions.

Añadir en `requirements.txt`:

```
google-genai>=1.0.0
```

(Actualizar versión según documentación oficial.)

### 8.2 Variables de entorno

- `GEMINI_API_KEY`: Clave de API de Google AI / Gemini. Obligatoria para informes y audio TTS.
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`: Para envío de informes por correo. Gmail requiere Contraseña de aplicación (no la contraseña normal).
- **Modelos (opcionales)** – Si no se definen, se usan los valores por defecto. Útil para actualizar modelos sin tocar código:
  - `GEMINI_MODEL_FLASH`: modelo para texto (About, resumen previo a TTS). Default: `gemini-2.5-flash`
  - `GEMINI_MODEL_TTS`: modelo para generación de audio. Default: `gemini-3.1-flash-tts-preview`
  - `GEMINI_AGENT_DEEP_RESEARCH`: agente para informes Deep Research. Default: `deep-research-max-preview-04-2026`
- Comportamiento si GEMINI_API_KEY no está configurada: deshabilitar botones de generación y mostrar mensaje informativo.

### 8.3 Mejoras UX (Ene 2026)

- **Toast notifications**: Sustituidos los `alert()` del navegador por notificaciones toast integradas (verde éxito, rojo error) en el detalle de informes.
- **Botón Volver**: El enlace "← Volver" usa `history.back()` para regresar a portfolio o watchlist según la página de origen; fallback a dashboard si no hay historial.
- **Visualización del informe**: Estilos CSS para `.report-markdown` (encabezados, tablas, listas, blockquotes) mejoran la legibilidad del contenido Markdown.
- **Generación paralela**: Informes y audios se generan en hilos independientes; se pueden solicitar varios assets sin esperar a que termine el anterior.

---

## 9. Seguridad y consideraciones

- **API Key:** No exponer en frontend. Todas las llamadas a Gemini desde el backend.
- **Validación de ownership:** Verificar siempre que el asset está en watchlist del usuario antes de generar o mostrar informes.
- **Rate limiting:** De momento sin límite por usuario; se puede añadir en el futuro.
- **Contenido generado:** Los informes son generados por IA. Incluir aviso de que no constituyen asesoramiento financiero.

---

## 10. Formato del contenido del informe

- **Recomendación inicial:** Markdown.
- El prompt a Deep Research debe incluir instrucciones de formato, por ejemplo:
  - "Formatea la salida en Markdown con encabezados, listas y párrafos claros."
  - "Incluye las secciones que consideres relevantes para un inversor."
- En el frontend: usar una librería como `marked` o `markdown-it` para renderizar Markdown a HTML.
- Si en pruebas el Markdown no es satisfactorio, se puede cambiar a solicitar HTML explícitamente en el prompt.

---

## 11. Plan de implementación sugerido (orden de fases)

1. **Fase 1 – Base de datos**
   - Crear tablas `report_settings`, `company_reports`, `asset_about_summary`.
   - Migraciones Flask-Migrate.
   - Modelos SQLAlchemy.

2. **Fase 2 – Servicio Gemini**
   - Servicio para resumen rápido (`generate_content`).
   - Servicio para Deep Research (Interactions API, background, poll).
   - Manejo de errores y timeouts.

3. **Fase 3 – API y lógica de negocio**
   - Endpoints de report-settings.
   - Endpoints de informes y de resumen "About the Company".
   - Lógica de límite de 5 informes y borrado en cascada.

4. **Fase 4 – UI Asset Detail**
   - Renombrar tab a "Overview", quitar Precio Anterior y Cambio del Día.
   - Añadir "About the Company" y botón "Generar resumen".
   - Nueva tab "Informes" con listado y detalle.
   - Modal/sección de Ajustes para descripción y puntos.
   - Botón "Generar informe" con estado deshabilitado/habilitado según report_settings.

5. **Fase 5 – UI Watchlist**
   - Botón "Generar informe" en columna ACCIONES (deshabilitado si no hay descripción).

6. **Fase 6 – Integración y pruebas**
   - Probar flujo completo de informe y de resumen.
   - Probar borrado en cascada al eliminar de watchlist.
   - Verificar comportamiento cuando no hay `GEMINI_API_KEY`.

---

## 12. Decisiones confirmadas (resumen)

| Aspecto                         | Decisión                                                                 |
|--------------------------------|---------------------------------------------------------------------------|
| Deep Research                  | Sí, disponible vía API de Interactions; usar `background=True` y poll    |
| Plantilla por usuario          | Sí, en `report_settings` (o equivalente)                                 |
| Alcance                        | Solo assets en watchlist (cartera o seguimiento)                         |
| Botón sin descripción          | Deshabilitado hasta que exista descripción guardada                      |
| Resumen "About the Company"    | Siempre con nombre, símbolo e ISIN de BD; sin contexto extra             |
| Máximo informes por asset      | 5; al 6º se borra el más antiguo                                         |
| Borrado al salir de watchlist  | Se borran todos los informes y el resumen del asset                      |
| Formato informe                | Markdown (recomendado); renderizar a HTML en frontend                    |
| Dos tipos de API               | Deep Research (Interactions) y resumen rápido (`generate_content`)       |

---

## 13. Documentación relacionada

- **`GEMINI_IA.md`** — Documento oficial de integración Gemini (modelos, configuración, arquitectura general)
- **`env.example`** — Plantilla de variables de entorno

---

*Documento creado el 29 de enero de 2026. Revisar antes de implementar por posibles actualizaciones de la API de Gemini.*
