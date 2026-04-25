"""
Servicio para integración con Google Gemini API.
- Resumen "About the Company": generate_content (rápido, síncrono)
- Informe Deep Research: Interactions API (background, poll)
- Audio informe: guion estilo podcast (texto) + TTS multi-locutor gemini-3.1-flash-tts-preview
"""
import os
import time
import logging
from typing import Callable, Optional, Tuple

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

Requisitos (español, solo cuerpo de texto, sin título ni saludos):
- Entre 80 y 200 palabras, en varias frases o 2-3 párrafos breves. No basta con una sola oración.
- Incluye qué hace la compañía (actividad, productos o servicios principales) y, si aplica, sector, tipo de clientes o mercados relevantes.
- Evita muletillas genéricas; sé concreto. Si faltan datos públicos, indícalo con una frase al final sin inventar cifras."""

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

Formatea la salida en Markdown con encabezados, listas y párrafos claros.
Incluye las secciones que consideres relevantes para un inversor."""

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        agent_name = _get_agent_deep_research()

        if on_status_update:
            on_status_update('processing', 'Iniciando investigación...')

        interaction = client.interactions.create(
            input=prompt,
            agent=agent_name,
            background=True,
            store=True,  # Requerido por la API para background=True
        )

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
PODCAST_MAX_WORDS = 1200

# Guion estilo NotebookLM: dos voces (nombres deben coincidir con MultiSpeakerVoiceConfig)
PODCAST_SCRIPT_PROMPT = f"""Actúa como un productor de podcasts experto. Basándote en el informe de investigación adjunto, genera un guion de conversación entre dos anfitriones, **{PODCAST_SPEAKER_1}** y **{PODCAST_SPEAKER_2}**.

**Reglas del guion:**
1. **Tono:** Conversacional, animado y humano. Evita que parezca que están leyendo un documento.
2. **Estructura:** {PODCAST_SPEAKER_1} suele introducir los temas y {PODCAST_SPEAKER_2} aporta detalles curiosos o explicaciones con analogías sencillas.
3. **Dinámica:** Deben interrumpirse educadamente, usar muletillas naturales (como "ah", "claro", "mira") e incluir reacciones emocionales ligeras.
4. **Etiquetas de audio:** Inserta etiquetas entre corchetes como [laughs], [short pause], [excited] o [thoughtful] en momentos clave (no abuses).
5. **Formato de salida (obligatorio):** Cada intervención en su propia línea, con prefijo exacto `{PODCAST_SPEAKER_1}:` o `{PODCAST_SPEAKER_2}:` (respetando mayúsculas y el acento en Álex). Ejemplo:
{PODCAST_SPEAKER_1}: [entusiasta] ¡Hola a todos! Hoy tenemos un tema interesante…
{PODCAST_SPEAKER_2}: [interesado] Claro, y lo que vimos en el informe te va a sorprender. [short pause] Empecemos con…

6. **Extensión (crítico):** El guion completo, en español, debe tener **como máximo {PODCAST_MAX_WORDS} palabras** en total. Cuenta antes de entregar. Objetivo: ~6 minutos de audio a ritmo natural.

No añadas título, introducción al lector ni markdown: **solo** las líneas del guion."""


def _shorten_podcast_script_if_needed(
    client, script: str, model: str, max_words: int
) -> str:
    from google.genai import types

    w = _count_words(script)
    if w <= max_words:
        return script
    resp = client.models.generate_content(
        model=model,
        contents=f"""Eres un editor de podcasts. El guion tiene {w} palabras; debe quedar en **máximo {max_words} palabras** en total.
Conserva el tono, la estructura y los prefijos exactos "{PODCAST_SPEAKER_1}:" y "{PODCAST_SPEAKER_2}:" en cada intervención. Conserva [etiquetas] útiles.
No añadas comentarios: solo el guion.

GUIÓN:
{script}
""",
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not resp or not resp.text:
        raise GeminiServiceError('No se pudo acortar el guion de podcast')
    return _strip_markdown_fences(resp.text.strip())


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
                    temperature=0.45,
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
            script = _shorten_podcast_script_if_needed(client, script, model, PODCAST_MAX_WORDS)
            if f'{PODCAST_SPEAKER_1}:' not in script or f'{PODCAST_SPEAKER_2}:' not in script:
                raise GeminiServiceError('Tras acortar, el guion perdió el formato de hablantes')
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
    """Paso 2: TTS con gemini-3.1-flash-tts-preview y dos voces (Charon + Puck)."""
    import wave
    from google.genai import types

    tts_user = f"""Escena: dos periodistas financieros en un estudio moderno. Estilo: dinámico y accesible para quien empieza en inversión.
Interpreta el texto como conversación con dos hablantes, {PODCAST_SPEAKER_1} (voz informativa) y {PODCAST_SPEAKER_2} (más animada, analogías sencillas). Respeta las [etiquetas] entre corchetes.

{script.strip()}"""

    try:
        multi = types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(
                    speaker=PODCAST_SPEAKER_1,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Charon')
                    ),
                ),
                types.SpeakerVoiceConfig(
                    speaker=PODCAST_SPEAKER_2,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Puck')
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
            speech_config=types.SpeechConfig(multi_speaker_voice_config=multi),
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


def generate_report_tts_audio(report_content: str, output_path: str) -> None:
    """
    Genera un audio resumen estilo "NotebookLM": dos locutores en conversación (Álex y Taylor).

    1) Modelo de texto (``GEMINI_MODEL_PODCAST_SCRIPT`` / por defecto flash): guion con etiquetas
       [laughs], [short pause], etc., máximo 1.200 palabras.
    2) ``gemini-3.1-flash-tts-preview`` con ``MultiSpeakerVoiceConfig``: voces Charon (Álex) y
       Puck (Taylor), una sola petición TTS (PCM 24 kHz mono → WAV).

    Args:
        report_content: Contenido Markdown del informe
        output_path: Ruta absoluta donde guardar el WAV

    Raises:
        GeminiServiceError: Si falla la generación
    """
    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError('GEMINI_API_KEY no configurada')

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        script = generate_podcast_script_from_report(report_content, client)
        _synthesize_multispeaker_podcast_wav(client, script, output_path)
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
