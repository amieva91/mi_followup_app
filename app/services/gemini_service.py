"""
Servicio para integración con Google Gemini API.
- Resumen "About the Company": generate_content (rápido, síncrono)
- Informe Deep Research: Interactions API (background, poll)
- Audio informe: guion estilo podcast (texto) + TTS multi-locutor gemini-3.1-flash-tts-preview
"""
import os
import time
import logging
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


class GeminiServiceError(Exception):
    """Error en el servicio Gemini"""
    pass


def _get_api_key() -> Optional[str]:
    """Obtener API key de Gemini desde variables de entorno"""
    raw = os.environ.get('GEMINI_API_KEY')
    return raw.strip() if raw else None


def _get_model_flash() -> str:
    """Modelo para texto (About, resumen TTS). Default: gemini-2.5-flash"""
    return os.environ.get('GEMINI_MODEL_FLASH') or 'gemini-2.5-flash'


def _get_model_tts() -> str:
    """Modelo para generación de audio TTS. Default: gemini-3.1-flash-tts-preview"""
    return os.environ.get('GEMINI_MODEL_TTS') or 'gemini-3.1-flash-tts-preview'


def _get_model_podcast_script() -> str:
    """Modelo de texto para guion estilo podcast (dos locutores). Default: mismo que flash."""
    return os.environ.get('GEMINI_MODEL_PODCAST_SCRIPT') or _get_model_flash()


def _get_podcast_script_temperature() -> float:
    """
    Temperatura para el guion (NotebookLM). Por defecto ~0,82 (más natural; el límite va en el prompt).
    Rango recomendado 0,7–1,0. Override: GEMINI_PODCAST_SCRIPT_TEMPERATURE.
    """
    raw = os.environ.get('GEMINI_PODCAST_SCRIPT_TEMPERATURE')
    if raw is None or str(raw).strip() == '':
        return 0.82
    try:
        return max(0.0, min(1.0, float(str(raw).strip().replace(',', '.'))))
    except ValueError:
        return 0.82


def _get_agent_deep_research() -> str:
    """Agente para informes Deep Research. Default: deep-research-preview-04-2026 (más ágil; Max vía env)."""
    return os.environ.get('GEMINI_AGENT_DEEP_RESEARCH') or 'deep-research-preview-04-2026'


def is_gemini_available() -> bool:
    """True si GEMINI_API_KEY está configurada"""
    return bool(_get_api_key())


def generate_about_summary(asset) -> str:
    """
    Genera un resumen corto "About the Company" usando generate_content.
    Síncrono, respuesta rápida (segundos).

    Args:
        asset: Objeto Asset con name, symbol, isin

    Returns:
        str: Resumen generado

    Raises:
        GeminiServiceError: Si no hay API key o falla la llamada
    """
    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError('GEMINI_API_KEY no configurada')

    name = asset.name or 'Desconocida'
    symbol = asset.symbol or ''
    isin = asset.isin or ''

    prompt = f"""Escribe un resumen "About" de la empresa **{name}** para alguien que la ve en una cartera de inversión.
Símbolo: {symbol or 'N/A'} | ISIN: {isin or 'N/A'}

Requisitos (español, sin saludos; salida en **Markdown mínimo** legible en pantalla):
- Entre 80 y 200 palabras. Estructura sugerida: 1) un párrafo introductorio; 2) opcionalmente **una lista con viñetas** (2–4 ítems) bajo un subtítulo en **## Actividad** o similar, con puntos concretos (qué hace, mercados, segmento); 3) cierre con una frase si faltan datos públicos (sin inventar cifras).
- Usa **negritas** en términos clave (producto, segmento, sede) para escaneo visual; no uses tablas; no uses bloques de código; no añadas H1; como mucho un **##** y **###** si hace falta.
- Tono: claro, inversor; evita muletillas genéricas.
- Sin título de documento al estilo "Informe" ni meta-comentarios al lector."""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        last_error = None
        max_retries = 3
        retry_delay = 65  # segundos (la API suele indicar ~60s)

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=_get_model_flash(),
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.35,
                        # 2.5 Flash cuenta el razonamiento interno contra max_output_tokens; si
                        # no se limita, la respuesta visible puede quedar truncada a mitad de frase.
                        max_output_tokens=1024,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                if response and response.text:
                    out = response.text.strip()
                    cands = getattr(response, "candidates", None) or []
                    if cands and cands[0].finish_reason and "MAX_TOKENS" in str(
                        cands[0].finish_reason
                    ).upper():
                        logger.warning(
                            "Resumen About: finish_reason=MAX_TOKENS (%s chars).",
                            len(out),
                        )
                    return out
                raise GeminiServiceError('Respuesta vacía de Gemini')
            except Exception as e:
                last_error = e
                err_str = str(e).upper()
                # 429 RESOURCE_EXHAUSTED: reintentar tras esperar
                if attempt < max_retries - 1 and ('429' in err_str or 'RESOURCE_EXHAUSTED' in err_str):
                    logger.warning('Gemini 429, reintento %s/%s en %ss: %s', attempt + 1, max_retries, retry_delay, e)
                    time.sleep(retry_delay)
                else:
                    raise

    except ImportError as e:
        raise GeminiServiceError(f'Paquete google-genai no instalado: {e}')
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.exception('Error generando resumen About: %s', e)
        raise GeminiServiceError(str(e))


def _extract_interaction_text(interaction) -> str:
    """Junta el texto de todos los bloques de salida (outputs) de la interacción."""
    outputs = getattr(interaction, 'outputs', None) or []
    parts = []
    for block in outputs:
        t = getattr(block, 'text', None)
        if t and str(t).strip():
            parts.append(str(t).strip())
    return '\n\n'.join(parts).strip() if parts else ''


def run_deep_research_report(
    asset_name: str,
    asset_symbol: str,
    asset_isin: str,
    description: str,
    points: list,
    on_status_update=None,
    poll_interval_seconds: int = 15,
    max_wait_seconds: int = 6 * 3600,
    on_interaction_created: Optional[Callable[[str], None]] = None,
) -> Tuple[str, str]:
    """
    Ejecuta informe Deep Research en segundo plano (polling hasta completar).
    Llama a la API de Interactions con background=True y hace poll hasta completed/failed.

    Args:
        asset_name: Nombre de la empresa
        asset_symbol: Símbolo del activo
        asset_isin: ISIN del activo
        description: Descripción de la investigación (obligatorio)
        points: Lista de puntos/preguntas opcionales
        on_status_update: Callback(opcional) que recibe (status, message) para actualizar UI
        poll_interval_seconds: Segundos entre cada poll
        max_wait_seconds: Máximo tiempo de espera (evita bucles infinitos si la API no termina)
        on_interaction_created: Callback con interaction_id nada más crear (para guardar en BD)

    Returns:
        tuple: (status, content_or_error)
        - ('completed', content) si éxito
        - ('failed', error_msg) si falla
    """
    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError('GEMINI_API_KEY no configurada')

    name = asset_name or 'Desconocida'
    symbol = asset_symbol or ''
    isin = asset_isin or ''

    points_text = ''
    if points:
        points_text = '\nPuntos a tratar:\n' + '\n'.join(f'- {p}' for p in points if p and str(p).strip())

    prompt = f"""Investiga y genera un informe detallado sobre la empresa {name}.
Símbolo: {symbol or 'N/A'} | ISIN: {isin or 'N/A'}

Descripción de la investigación:
{description}
{points_text}

**Formato y presentación (obligatorio):**
- Usa un **diseño editorial profesional** en **Markdown** avanzado: **H1** para el título del informe, **H2/H3** para secciones, listas y tablas.
- Incluye al inicio de cada sección principal un bloque **Key takeaways** (3–5 viñetas) con negritas en conceptos clave.
- Incluye **tablas comparativas** para cifras, márgenes, PER, deuda, o frente a competidores cuando haya datos.
- Si aplica, representa en tabla una **puntuación del foso o ventaja competitiva** (no solo texto narrativo) con criterios y notas.
- Aprovecha la **visualización nativa** del agente (gráficos, comparativas, diagramas de flujo de ingresos) cuando aporte claridad, sin sustituir el rigor.
- Añade listas con viñetas o emojis con moderación para escaneo visual (sin exceso).
- El estilo ha de resultar claro al leerse en la **web y en el correo** (bloques no demasiado largos, títulos descriptivos).
- Idioma: **español (España)**. Tonos: analítico, orientado a inversor.

**Contenido:** cubre con rigor lo que pida la descripción; prioriza análisis accionable frente a rellano."""

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        agent_name = _get_agent_deep_research()

        if on_status_update:
            on_status_update('processing', 'Iniciando investigación...')

        # Activa resúmenes de razonamiento y gráficos/infografías nativos cuando el SDK/API lo soporten.
        deep_agent_config = {
            'type': 'deep-research',
            'visualization': 'auto',
            'thinking_summaries': 'auto',
        }
        interaction = None
        last_create_err: Optional[Exception] = None
        for with_agent_cfg in (True, False):
            try:
                kwargs = {
                    'input': prompt,
                    'agent': agent_name,
                    'background': True,
                    'store': True,  # Requerido por la API para background=True
                }
                if with_agent_cfg:
                    kwargs['agent_config'] = deep_agent_config
                interaction = client.interactions.create(**kwargs)
                break
            except Exception as ex:
                last_create_err = ex
                if with_agent_cfg:
                    logger.warning(
                        'interactions.create con agent_config falló; reintento sin: %s',
                        ex,
                    )
                    continue
                raise
        if interaction is None and last_create_err:
            raise last_create_err

        interaction_id = interaction.id if hasattr(interaction, 'id') else str(interaction)
        logger.info('Deep Research iniciado: agent=%s interaction_id=%s', agent_name, interaction_id)
        if on_interaction_created:
            try:
                on_interaction_created(str(interaction_id)[:100])
            except Exception as cb_err:
                logger.warning('on_interaction_created falló: %s', cb_err)

        if on_status_update:
            on_status_update('processing', 'Investigando en segundo plano...')

        deadline = time.monotonic() + max_wait_seconds
        poll_n = 0
        last_logged_status = None

        while True:
            if time.monotonic() > deadline:
                msg = (
                    f'Tiempo de espera agotado ({max_wait_seconds // 3600} h) con la API aún en curso. '
                    f'interaction_id={interaction_id}. Puedes reintentar o usar GEMINI_AGENT_DEEP_RESEARCH=deep-research-preview-04-2026'
                )
                logger.error('Deep Research timeout: %s', msg)
                if on_status_update:
                    on_status_update('failed', msg)
                return ('failed', msg)

            interaction = client.interactions.get(interaction_id)
            raw = getattr(interaction, 'status', None)
            status = (raw or 'unknown')
            if isinstance(status, str):
                status = status.lower()
            else:
                status = str(getattr(status, 'value', status)).lower()

            if status != last_logged_status or poll_n % 8 == 0:
                logger.info('Deep Research poll: id=%s status=%s', interaction_id, status)
                last_logged_status = status
            poll_n += 1

            if status == 'completed':
                text = _extract_interaction_text(interaction) or 'Informe vacío'
                if on_status_update:
                    on_status_update('completed', 'Informe completado')
                return ('completed', text)

            if status == 'failed':
                error_msg = getattr(interaction, 'error', 'Error desconocido') or 'Error desconocido'
                if hasattr(error_msg, 'message'):
                    error_msg = error_msg.message
                error_str = str(error_msg)
                logger.error('Deep Research falló: %s', error_str)
                if on_status_update:
                    on_status_update('failed', error_str)
                return ('failed', error_str)

            if status in ('cancelled', 'canceled'):
                msg = 'La interacción fue cancelada en el servicio de Gemini.'
                logger.error('Deep Research: %s', msg)
                return ('failed', msg)

            if status == 'requires_action':
                msg = (
                    'La API devolvió requires_action (pendiente de acción humana en Google). '
                    'No se puede completar en esta integración. Prueba otra clave de proyecto o el agente deep-research-preview-04-2026.'
                )
                logger.error('Deep Research: %s', msg)
                if on_status_update:
                    on_status_update('failed', msg)
                return ('failed', msg)

            if status not in ('in_progress', 'pending', 'running', 'unknown', 'active'):
                logger.warning('Deep Research: estado inesperado %s, sigo haciendo poll', status)

            time.sleep(poll_interval_seconds)
            if on_status_update:
                on_status_update('processing', f'Investigando... (estado: {status})')

    except ImportError as e:
        raise GeminiServiceError(f'Paquete google-genai no instalado: {e}')
    except Exception as e:
        logger.exception('Error en Deep Research: %s', e)
        raise GeminiServiceError(str(e))


def _count_words(text: str) -> int:
    return len((text or '').split())


def _strip_markdown_fences(text: str) -> str:
    s = (text or '').strip()
    if not s.startswith('```'):
        return s
    lines = s.split('\n')
    if lines and lines[0].startswith('```'):
        lines = lines[1:]
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines).strip()


PODCAST_SPEAKER_1 = 'Álex'
PODCAST_SPEAKER_2 = 'Taylor'

# Presupuesto (español ~150 wpm, 6 min ≈ 900). Margen de seguridad antes de TTS.
PODCAST_SCRIPT_TARGET_MIN = 850
PODCAST_SCRIPT_TARGET_MAX = 900
PODCAST_HARD_MAX_WORDS = 950
# Tres actos: intro ~10 %, cuerpo ~80 %, cierre ~10 % (guía para el modelo, ~900 p. total)
PODCAST_ACT1_WORDS_GUIDE = 90
PODCAST_ACT2_WORDS_GUIDE = 720
PODCAST_ACT3_WORDS_GUIDE = 90

# Debe coincidir con nombres en el guion (TTS: Charon / Kore)
PODCAST_TTS_VOICE_ALEX = 'Charon'  # voz masculina
PODCAST_TTS_VOICE_TAYLOR = 'Kore'  # voz femenina

# Prompt maestro: planificación por segmentos, estilo Google / NotebookLM
PODCAST_SCRIPT_PROMPT = f"""Actúa como un guionista profesional de podcasts. Tu misión es convertir el informe de Deep Research adjunto en un diálogo natural entre **{PODCAST_SPEAKER_1}** (hombre) y **{PODCAST_SPEAKER_2}** (mujer).

**REGLAS DE ORO DE DURACIÓN (presupuesto de palabras):**
1. **Límite estricto:** el guion debe situarse en **{PODCAST_SCRIPT_TARGET_MIN}–{PODCAST_SCRIPT_TARGET_MAX} palabras**. **Nunca** superes **{PODCAST_HARD_MAX_WORDS}** palabras.
2. **Matemática:** en podcast conversacional en español (~150 palabras por minuto), unos **900 palabras** ≈ **6 minutos**. Planifica con ese “presupuesto” desde el primer borrador, no escribas de más pensando en recortar después.
3. **Distribución en tres actos (orientación de tiempo):**
   - **Acto 1 — Introducción (~10 %, ~{PODCAST_ACT1_WORDS_GUIDE} palabras):** gancho y presentación del tema (no más de **100** palabras en la práctica).
   - **Acto 2 — Cuerpo (~80 %, ~{PODCAST_ACT2_WORDS_GUIDE} palabras):** **solo 3** puntos de hallazgo (los más impactantes; **no** intentes cubrir todo el informe).
   - **Acto 3 — Cierre (~10 %, ~{PODCAST_ACT3_WORDS_GUIDE} palabras):** conclusión y despedida clara al oyente (reserva unas **80–100** palabras para el cierre con despedida natural).
4. **Priorización:** profundizar en 3 ideas vale más que 10 comentarios superficiales.

**RESTRICCIONES CRÍTICAS DE MARCA:**
1. **Prohibido inventar nombres:** no le pongas nombre al «podcast» ni al programa. No uses frases del tipo «Bienvenidos a…» o títulos de radio inventados.
2. **Inicio directo:** la primera intervención debe sonar a conversación real (p. ej. «Hola {PODCAST_SPEAKER_2}, he estado revisando el informe sobre…» y entrar al fondo), sin parrilla de emisora.
3. **Sin introducciones de radio ficticias:** evita muletillas que hagan creer que es un programa con nombre. El foco es **solo** el contenido del informe de investigación.

**REGLAS DE ESTILO (NotebookLM):**
- **Voces:** usa los prefijos exactos **{PODCAST_SPEAKER_1}:** y **{PODCAST_SPEAKER_2}:** en cada intervención.
- **Tono:** {PODCAST_SPEAKER_1} informativo y profesional. {PODCAST_SPEAKER_2} curiosa, con analogías sencillas. **Acento y registro: español de España (peninsular), profesional.**
- **Naturalidad:** interrupciones breves (por ejemplo: «Espera, ¿dices que…?», «Exacto»), [laughs] y [sigh] con moderación.
- **Pausas:** [short pause] entre cambios de tema. **PROHIBIDO** [long pause], [long silence] o silencios largos (desvían el cronómetro sin contar como palabra).
- **Cierre:** el **último** turno debe ser una despedida clara hacia el oyente.

**Formato de salida:** una réplica por línea; **solo** el guion, sin título, sin markdown y sin comentarios al lector."""


def _synthesis_reduce_script_for_tts(
    client,
    script: str,
    model: str,
    current_w: int,
) -> str:
    """
    Reducción por síntesis: se pide reescribir apretando el cuerpo y manteniendo intro/cierre
    (no recorte mecánico; solo si el guion > HARD_MAX).
    """
    from google.genai import types

    if current_w <= PODCAST_HARD_MAX_WORDS:
        return script
    intro_hint = f'{PODCAST_SPEAKER_1}:'  # ancla mínima para el modelo
    resp = client.models.generate_content(
        model=model,
        contents=f"""Este guion de podcast tiene **{current_w} palabras**; es **demasiado largo** para nuestro audio (máximo **{PODCAST_HARD_MAX_WORDS}** palabras antes de TTS, ideal **{PODCAST_SCRIPT_TARGET_MIN}–{PODCAST_SCRIPT_TARGET_MAX}**).

Tarea: **reducción por síntesis** (no resumas borrando palabra a palabra a lo brusco):
1. Mantén la **introducción** (aprox. las primeras intervenciones hasta plantear el tema) lo más fiel en tono, pero puedes ajustar frases.
2. Mantén el **cierre** y la **despedida final** (última intervención clara hacia el oyente) con la misma intención.
3. **Aplica el ahorro principal al bloque central:** resume o fusiona el **segundo** o **tercer** hallazgo, elimina matices secundarios, recorta oraciones que repitan el informe.
4. Cada réplica: prefijo **{PODCAST_SPEAKER_1}:** o **{PODCAST_SPEAKER_2}:**. Sin [long pause].
5. El resultado final debe quedar en **{PODCAST_SCRIPT_TARGET_MIN}–{PODCAST_SCRIPT_TARGET_MAX}** palabras y **nunca** superar **{PODCAST_HARD_MAX_WORDS}** (cuenta al terminar).

Ancla mínima de apertura (puede variar ligeramente): la primera intervención debería seguir comenzando con algo como una línea que empiece por «{intro_hint}».

Solo el guion reescrito.

---
GUIÓN ACTUAL
---
{script}
""",
        config=types.GenerateContentConfig(
            temperature=0.55,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not resp or not resp.text:
        raise GeminiServiceError('No se pudo aplicar la reducción por síntesis al guion')
    return _strip_markdown_fences(resp.text.strip())


def _truncate_script_at_speaker_lines(script: str, max_words: int) -> str:
    """
    Último recurso: recorta el guion por turnos, sin romper el prefijo de hablante.
    """
    p1 = f'{PODCAST_SPEAKER_1}:'
    p2 = f'{PODCAST_SPEAKER_2}:'
    out: list[str] = []
    wcount = 0
    for line in (script or '').split('\n'):
        t = line.strip()
        if not t:
            continue
        if t.startswith(p1):
            rest = t[len(p1) :].strip()
            pref = p1
        elif t.startswith(p2):
            rest = t[len(p2) :].strip()
            pref = p2
        else:
            continue
        rest_words = rest.split()
        room = max_words - wcount
        if room <= 0:
            break
        take = min(len(rest_words), room)
        if take <= 0:
            break
        chunk = ' '.join(rest_words[:take])
        if take < len(rest_words):
            chunk = chunk + '…'
        out.append(f'{pref} {chunk}')
        wcount += take
        if take < len(rest_words) or wcount >= max_words:
            break
    if not out and script:
        words = (script or '').split()
        return ' '.join(words[: max_words]) if words else script
    return '\n\n'.join(out).strip()


def _ensure_script_ready_for_tts(client, script: str, model: str) -> str:
    """
    Solo se envía a TTS si el guion tiene ≤ ``PODCAST_HARD_MAX_WORDS`` palabras.
    Si el borrador inicial supera ese tope, se aplica **reducción por síntesis** (varias pasadas).
    El truncado mecánico es solo emergencia (no deseado).
    """
    s = script
    for attempt in range(5):
        n = _count_words(s)
        if n <= PODCAST_HARD_MAX_WORDS:
            return s
        logger.info(
            'Guion %s palabras > límite %s; reducción por síntesis (intento %s)',
            n,
            PODCAST_HARD_MAX_WORDS,
            attempt + 1,
        )
        s = _synthesis_reduce_script_for_tts(client, s, model, n)
    n = _count_words(s)
    if n > PODCAST_HARD_MAX_WORDS:
        logger.error(
            'Guion aún con %s palabras tras síntesis; truncado de emergencia (evitable con informe más corto)',
            n,
        )
        s = _truncate_script_at_speaker_lines(s, PODCAST_HARD_MAX_WORDS)
    return s


def generate_podcast_script_from_report(report_content: str, client) -> str:
    """
    Paso 1: convierte el informe en guion de conversación (estilo NotebookLM) para TTS multi-locutor.
    """
    from google.genai import types

    model = _get_model_podcast_script()
    body = (report_content or '').strip()
    if len(body) < 80:
        raise GeminiServiceError('Informe demasiado corto para generar guion de podcast')

    user_block = f"""{PODCAST_SCRIPT_PROMPT}

--- INFORME (markdown) ---
{body[:50000]}"""

    max_retries = 3
    retry_delay = 65
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_block,
                config=types.GenerateContentConfig(
                    temperature=_get_podcast_script_temperature(),
                    max_output_tokens=8192,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if not response or not response.text:
                raise GeminiServiceError('Respuesta vacía al generar el guion de podcast')
            script = _strip_markdown_fences(response.text.strip())
            if not script or _count_words(script) < 40:
                raise GeminiServiceError('Guion de podcast demasiado corto o inválido')
            if f'{PODCAST_SPEAKER_1}:' not in script or f'{PODCAST_SPEAKER_2}:' not in script:
                raise GeminiServiceError(
                    f'El guion debe incluir diálogos con prefijos "{PODCAST_SPEAKER_1}:" y "{PODCAST_SPEAKER_2}:"'
                )
            script = _ensure_script_ready_for_tts(client, script, model)
            if f'{PODCAST_SPEAKER_1}:' not in script or f'{PODCAST_SPEAKER_2}:' not in script:
                raise GeminiServiceError('Tras re-escribir, el guion perdió el formato de hablantes')
            return script
        except GeminiServiceError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e).upper()
            if attempt < max_retries - 1 and ('429' in err_str or 'RESOURCE_EXHAUSTED' in err_str):
                logger.warning('Gemini guion podcast 429, reintento %s/%s: %s', attempt + 1, max_retries, e)
                time.sleep(retry_delay)
            else:
                raise GeminiServiceError(str(e)) from e
    raise GeminiServiceError('No se pudo generar el guion de podcast')


def _synthesize_multispeaker_podcast_wav(client, script: str, output_path: str) -> None:
    """Paso 2: TTS con gemini-3.1-flash-tts-preview: voces fijas (Charon masculina, Kore femenina), ``language_code=es-ES``."""
    import wave
    from google.genai import types

    tts_user = f"""**Director de audio (léelo antes de hablar, no lo repitas en voz alta):** Accent: Peninsular Spanish from Spain. Neutral, professional, European Spanish intonation; avoid Latin American inflections. Voces con acento de España peninsular, claras y sin modismos de Hispanoamérica.

Escena: conversación de análisis en contexto de inversión, tono serio y cercano, **español de España (peninsular)**.
Interpreta el texto como diálogo con **dos interlocutores**:
- {PODCAST_SPEAKER_1}: voz **masculina** (timbre Charon, informativo).
- {PODCAST_SPEAKER_2}: voz **femenina** (timbre Kore, clara, analogías sencillas).
Respeta las [etiquetas] entre corchetes sin alargar silencios de forma exagerada.

{script.strip()}"""

    try:
        multi = types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(
                    speaker=PODCAST_SPEAKER_1,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=PODCAST_TTS_VOICE_ALEX
                        )
                    ),
                ),
                types.SpeakerVoiceConfig(
                    speaker=PODCAST_SPEAKER_2,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=PODCAST_TTS_VOICE_TAYLOR
                        )
                    ),
                ),
            ]
        )
    except AttributeError as e:
        raise GeminiServiceError(
            'Falta soporte multi-locutor en google-genai. Instala: pip install -U "google-genai>=1.16.0"'
        ) from e

    response = client.models.generate_content(
        model=_get_model_tts(),
        contents=tts_user,
        config=types.GenerateContentConfig(
            response_modalities=['AUDIO'],
            max_output_tokens=24576,
            speech_config=types.SpeechConfig(
                language_code='es-ES',
                multi_speaker_voice_config=multi,
            ),
        ),
    )
    all_pcm = _pcm_from_tts_response(response)
    if len(all_pcm) < 256:
        raise GeminiServiceError('Audio generado demasiado corto o vacío')
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(all_pcm)
    logger.info('Audio podcast multi-locutor guardado: %s (bytes_pcm=%s)', output_path, len(all_pcm))


def _pcm_from_tts_response(response) -> bytes:
    """Extrae PCM crudo de una respuesta generate_content con modalidad AUDIO."""
    import base64

    parts = getattr(response, 'candidates', []) or []
    if not parts:
        raise GeminiServiceError('Respuesta TTS vacía')
    content = parts[0].content
    inner_parts = getattr(content, 'parts', []) or []
    if not inner_parts:
        raise GeminiServiceError('Respuesta TTS sin partes de audio')
    inline = inner_parts[0].inline_data
    data = getattr(inline, 'data', None)
    if not data:
        raise GeminiServiceError('No hay datos de audio en la respuesta')
    if isinstance(data, str):
        return base64.b64decode(data)
    return data


def new_audio_progress_steps_state() -> list:
    """Estado inicial de pasos (guion → TTS) para UI y persistencia en BD."""
    return [
        {
            'id': 'script',
            'title': 'Guion 3 actos (≤950 p., estilo NotebookLM)',
            'status': 'loading',
            'model': _get_model_podcast_script(),
            'error': None,
        },
        {
            'id': 'tts',
            'title': 'Síntesis TTS (Charon + Kore, es-ES)',
            'status': 'pending',
            'model': _get_model_tts(),
            'error': None,
        },
    ]


def new_full_pipeline_progress_state() -> dict:
    """
    Guion (progreso unificado) para: informe Deep Research → guion → TTS → envío de correo.
    Se persiste en ``company_reports.audio_progress_json`` con ``full_pipeline: true``.
    """
    return {
        'full_pipeline': True,
        'caption': (
            'Proceso completo en segundo plano: informe, audio (es-ES) y envío por correo. '
            'Puedes salir; recibirás el informe y el audio en tu email.'
        ),
        'steps': [
            {
                'id': 'report',
                'title': 'Informe Deep Research',
                'status': 'loading',
                'model': _get_agent_deep_research(),
                'error': None,
            },
            {
                'id': 'script',
                'title': 'Guion 3 actos (≤950 p., estilo NotebookLM)',
                'status': 'pending',
                'model': _get_model_podcast_script(),
                'error': None,
            },
            {
                'id': 'tts',
                'title': 'Síntesis TTS (Charon + Kore, es-ES)',
                'status': 'pending',
                'model': _get_model_tts(),
                'error': None,
            },
            {
                'id': 'email',
                'title': 'Enviar informe y audio por correo',
                'status': 'pending',
                'model': None,
                'error': None,
            },
        ],
    }


def merge_full_pipeline_with_tts_progress(full_state: dict, tts_progress: dict) -> dict:
    """Incorpora los dos pasos del TTS (guion + audio) en el estado de pipeline de 4 pasos."""
    out = {**full_state, 'full_pipeline': True}
    steps = [dict(s) for s in (out.get('steps') or [])]
    tts_steps = (tts_progress or {}).get('steps') or []
    if len(steps) >= 3 and len(tts_steps) >= 1:
        for k in ('status', 'error', 'model'):
            if k in tts_steps[0] and tts_steps[0][k] is not None:
                steps[1][k] = tts_steps[0][k]
    if len(steps) >= 3 and len(tts_steps) >= 2:
        for k in ('status', 'error', 'model'):
            if k in tts_steps[1] and tts_steps[1][k] is not None:
                steps[2][k] = tts_steps[1][k]
    out['steps'] = steps
    return out


def generate_report_tts_audio(
    report_content: str,
    output_path: str,
    *,
    on_progress: Optional[Callable[[dict], None]] = None,
) -> None:
    """
    Genera un audio resumen estilo "NotebookLM": dos locutores en conversación (Álex y Taylor).

    1) Guion con **presupuesto por segmentos** (tres actos, 850–900 p. objetivo, techo 950 p.):
       temperatura configurable (``GEMINI_PODCAST_SCRIPT_TEMPERATURE``, p. ej. 0,82). Si el borrador
       supera 950 palabras, **reducción por síntesis** (no recorte brusco por defecto).
    2) ``gemini-3.1-flash-tts-preview`` con ``MultiSpeakerVoiceConfig``: **Charon (Álex)** y
       **Kore (Taylor)**, ``response_modalities=['AUDIO']``, PCM 24 kHz mono → WAV.

    Args:
        report_content: Contenido Markdown del informe
        output_path: Ruta absoluta donde guardar el WAV
        on_progress: Opcional. Recibe ``{"steps": [{id, title, status, model, error}, ...]}``
            en cada transición (``status``: pending, loading, ok, error).

    Raises:
        GeminiServiceError: Si falla la generación
    """
    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError('GEMINI_API_KEY no configurada')

    def emit(steps: list[Any]) -> None:
        if on_progress:
            on_progress({'steps': [dict(s) for s in steps]})

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        steps = new_audio_progress_steps_state()
        emit(steps)

        try:
            script = generate_podcast_script_from_report(report_content, client)
        except Exception as e:
            steps[0]['status'] = 'error'
            steps[0]['error'] = (str(e) or 'Error')[:4000]
            emit(steps)
            raise

        steps[0]['status'] = 'ok'
        steps[0]['error'] = None
        steps[1]['status'] = 'loading'
        emit(steps)

        try:
            _synthesize_multispeaker_podcast_wav(client, script, output_path)
        except Exception as e:
            steps[1]['status'] = 'error'
            steps[1]['error'] = (str(e) or 'Error')[:4000]
            emit(steps)
            raise

        steps[1]['status'] = 'ok'
        steps[1]['error'] = None
        emit(steps)

        logger.info(
            'TTS podcast completado: %s (palabras guion~%s)',
            output_path,
            _count_words(script),
        )

    except ImportError as e:
        raise GeminiServiceError(f'Paquete google-genai no instalado: {e}')
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.exception('Error generando TTS podcast: %s', e)
        raise GeminiServiceError(str(e))
