"""
Servicio para integración con Google Gemini API.
- Resumen "About the Company": generate_content (rápido, síncrono)
- Informe Deep Research: Interactions API (background, poll)
"""
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiServiceError(Exception):
    """Error en el servicio Gemini"""
    pass


def _get_api_key() -> Optional[str]:
    """Obtener API key de Gemini desde variables de entorno"""
    return os.environ.get('GEMINI_API_KEY')


def _get_model_flash() -> str:
    """Modelo para texto (About, resumen TTS). Default: gemini-2.0-flash"""
    return os.environ.get('GEMINI_MODEL_FLASH') or 'gemini-2.0-flash'


def _get_model_tts() -> str:
    """Modelo para generación de audio TTS. Default: gemini-2.5-flash-preview-tts"""
    return os.environ.get('GEMINI_MODEL_TTS') or 'gemini-2.5-flash-preview-tts'


def _get_agent_deep_research() -> str:
    """Agente para informes Deep Research. Default: deep-research-pro-preview-12-2025"""
    return os.environ.get('GEMINI_AGENT_DEEP_RESEARCH') or 'deep-research-pro-preview-12-2025'


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

    prompt = f"""En 3-5 líneas, describe brevemente qué hace la empresa {name}.
Símbolo: {symbol or 'N/A'} | ISIN: {isin or 'N/A'}
Respuesta concisa en español, sin introducciones."""

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
                        temperature=0.3,
                        max_output_tokens=256,
                    ),
                )
                if response and response.text:
                    return response.text.strip()
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


def run_deep_research_report(
    asset_name: str,
    asset_symbol: str,
    asset_isin: str,
    description: str,
    points: list,
    on_status_update=None,
    poll_interval_seconds: int = 15,
) -> tuple[str, str]:
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
        logger.info('Deep Research iniciado: interaction_id=%s', interaction_id)

        if on_status_update:
            on_status_update('processing', 'Investigando en segundo plano...')

        while True:
            interaction = client.interactions.get(interaction_id)
            status = getattr(interaction, 'status', str(interaction)).lower() if hasattr(interaction, 'status') else 'unknown'

            if status == 'completed':
                outputs = getattr(interaction, 'outputs', []) or []
                text = ''
                if outputs:
                    last_output = outputs[-1]
                    text = getattr(last_output, 'text', '') or str(last_output)
                if on_status_update:
                    on_status_update('completed', 'Informe completado')
                return ('completed', text.strip() or 'Informe vacío')

            if status == 'failed':
                error_msg = getattr(interaction, 'error', 'Error desconocido') or 'Error desconocido'
                if hasattr(error_msg, 'message'):
                    error_msg = error_msg.message
                error_str = str(error_msg)
                logger.error('Deep Research falló: %s', error_str)
                if on_status_update:
                    on_status_update('failed', error_str)
                return ('failed', error_str)

            time.sleep(poll_interval_seconds)
            if on_status_update:
                on_status_update('processing', f'Investigando... (estado: {status})')

    except ImportError as e:
        raise GeminiServiceError(f'Paquete google-genai no instalado: {e}')
    except Exception as e:
        logger.exception('Error en Deep Research: %s', e)
        raise GeminiServiceError(str(e))


def generate_report_tts_audio(report_content: str, output_path: str) -> None:
    """
    Genera un audio TTS resumen del informe usando Gemini.
    1. Usa gemini-2.0-flash para crear un resumen de 2-3 min lectura
    2. Usa gemini-2.5-flash-preview-tts para generar audio

    Args:
        report_content: Contenido Markdown del informe
        output_path: Ruta absoluta donde guardar el WAV

    Raises:
        GeminiServiceError: Si falla la generación
    """
    import wave

    api_key = _get_api_key()
    if not api_key:
        raise GeminiServiceError('GEMINI_API_KEY no configurada')

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # 1. Generar resumen corto para TTS (~500-800 palabras)
        summary_prompt = f"""Resume el siguiente informe de investigación de inversiones en un texto fluido 
para ser leído en voz alta. El resumen debe durar 2-3 minutos de lectura.
Incluye las conclusiones más importantes y recomendaciones. 
Texto directo, sin encabezados markdown ni listas con viñetas en el resultado.
Solo texto corrido, en español.

INFORME:
{report_content[:12000]}
"""

        transcript = client.models.generate_content(
            model=_get_model_flash(),
            contents=summary_prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=1500,
            ),
        )
        if not transcript or not transcript.text:
            raise GeminiServiceError('No se pudo generar el resumen para TTS')

        text_for_tts = transcript.text.strip()
        if len(text_for_tts) < 100:
            raise GeminiServiceError('Resumen demasiado corto para generar audio')

        # 2. Generar audio TTS
        tts_prompt = f"Lee el siguiente resumen en tono profesional e informativo, pausado y claro:\n\n{text_for_tts}"

        response = client.models.generate_content(
            model=_get_model_tts(),
            contents=tts_prompt,
            config=types.GenerateContentConfig(
                response_modalities=['AUDIO'],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Charon')
                    )
                ),
            ),
        )

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

        # data puede ser bytes o base64
        if isinstance(data, str):
            import base64
            pcm_data = base64.b64decode(data)
        else:
            pcm_data = data

        # Guardar WAV: PCM 24kHz, 1 canal, 16-bit
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_data)

        logger.info('Audio TTS guardado: %s', output_path)

    except ImportError as e:
        raise GeminiServiceError(f'Paquete google-genai no instalado: {e}')
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.exception('Error generando TTS: %s', e)
        raise GeminiServiceError(str(e))
