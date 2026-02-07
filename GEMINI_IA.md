# Gemini AI / API - Documentación Oficial

Documento de referencia para la integración de **Google Gemini** en FollowUp. Centraliza modelos, configuración y funcionalidades de IA. Se actualizará conforme se añadan nuevas capacidades.

---

## 1. Resumen

La aplicación utiliza la API de **Google Gemini** para:

| Funcionalidad | Descripción |
|---------------|-------------|
| **Resumen "About the Company"** | Descripción corta de la empresa (3-5 líneas) |
| **Informes Deep Research** | Informes de inversión detallados basados en plantillas |
| **Audio TTS** | Resumen en audio del informe (text-to-speech) |

Todas las llamadas se realizan desde el backend. La API key nunca se expone al frontend.

---

## 2. Modelos en uso

| Uso | Variable de entorno | Modelo por defecto |
|-----|---------------------|--------------------|
| Texto (About, resumen previo a TTS) | `GEMINI_MODEL_FLASH` | `gemini-2.0-flash` |
| Audio TTS | `GEMINI_MODEL_TTS` | `gemini-2.5-flash-preview-tts` |
| Informes Deep Research | `GEMINI_AGENT_DEEP_RESEARCH` | `deep-research-pro-preview-12-2025` |

Las variables son opcionales. Si no se definen, se usan los valores por defecto. Permiten actualizar modelos sin cambiar código cuando Google lance nuevas versiones.

---

## 3. Configuración

### 3.1 Variables de entorno

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | Sí | Clave de API de Google AI. Obtener en [Google AI Studio](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL_FLASH` | No | Modelo para texto. Default: `gemini-2.0-flash` |
| `GEMINI_MODEL_TTS` | No | Modelo para audio TTS. Default: `gemini-2.5-flash-preview-tts` |
| `GEMINI_AGENT_DEEP_RESEARCH` | No | Agente para informes Deep Research. Default: `deep-research-pro-preview-12-2025` |

### 3.2 Dependencias

```
google-genai>=1.0.0
```

### 3.3 Comportamiento sin API key

Si `GEMINI_API_KEY` no está configurada:

- Los botones de generación de informes y audio se deshabilitan
- Se muestra mensaje informativo al usuario

---

## 4. Arquitectura

### 4.1 Servicio principal

**`app/services/gemini_service.py`**

| Función | Modo | Descripción |
|---------|------|-------------|
| `generate_about_summary(asset)` | Síncrono | Resumen corto "About the Company" |
| `run_deep_research_report(...)` | Asíncrono (poll) | Informe completo vía Interactions API |
| `generate_report_tts_audio(content, path)` | Síncrono | Genera WAV del resumen en audio |

### 4.2 Rutas (API)

- `POST /portfolio/asset/<id>/about/generate` — Resumen About
- `POST /portfolio/asset/<id>/reports/generate` — Iniciar informe Deep Research
- `POST /portfolio/asset/<id>/reports/<id>/generate-audio` — Iniciar TTS
- `GET /portfolio/asset/<id>/reports/<id>/audio` — Descargar/reproducir WAV

### 4.3 Persistencia

- **Informes**: `company_reports` (contenido Markdown, estado, audio_path, etc.)
- **Resumen About**: `asset_about_summary`
- **Audio**: archivos WAV en `output/reports_audio/`

---

## 5. Flujos de uso

### 5.1 Resumen About the Company

1. Usuario pulsa "Generar resumen" en Overview del asset
2. Backend valida: asset en watchlist
3. Llamada síncrona a `generate_content` con `gemini-2.0-flash`
4. Guardar en `asset_about_summary`
5. Devolver al frontend

### 5.2 Informe Deep Research

1. Usuario selecciona plantilla y pulsa "Generar informe"
2. Se crea registro en `company_reports` con `status=pending`
3. Thread en background llama a Interactions API (`background=True`)
4. Polling hasta `completed` o `failed`
5. Guardar contenido Markdown en BD

### 5.3 Audio TTS

1. Usuario pulsa "Generar audio resumen" en informe completado
2. Thread en background:
   - Resumen del informe con `gemini-2.0-flash`
   - TTS con `gemini-2.5-flash-preview-tts` (voz Charon)
   - Guardar WAV en `output/reports_audio/report_{id}.wav`
3. Actualizar `company_reports.audio_path`, `audio_status=completed`

---

## 6. Consideraciones

- **Rate limiting**: Retry automático en 429 (RESOURCE_EXHAUSTED)
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
| Audio TTS del informe | ✅ Implementado |
| Envío de informe por correo (con audio adjunto) | ✅ Implementado |

---

*Última actualización: Enero 2026*
