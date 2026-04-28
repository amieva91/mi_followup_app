"""
Servicio para integración con Google Gemini API.
- Resumen "About the Company": generate_content (rápido, síncrono)
- Informe Deep Research: Interactions API (background, poll)
- Audio informe: guion estilo podcast (texto) + TTS multi-locutor ``gemini-3.1-flash-tts-preview``
  (API ``generateContent`` del SDK; no es el producto independiente «NotebookLM / Podcasts» de Google,
  pero replica el patrón guion → audio multispeaker de la documentación oficial).
"""
import os
import re
import base64
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


def _get_tts_synthesis_temperature() -> float:
    """
    Temperatura solo en la llamada al modelo TTS (audio), no al guion.
    Valores altos en audio largo pueden aumentar artefactos; por defecto 0,65.
    Override: GEMINI_TTS_TEMPERATURE.
    """
    raw = os.environ.get('GEMINI_TTS_TEMPERATURE')
    if raw is None or str(raw).strip() == '':
        return 0.65
    try:
        return max(0.0, min(1.0, float(str(raw).strip().replace(',', '.'))))
    except ValueError:
        return 0.65


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
    """Agente para informes Deep Research. Default: ``deep-research-max-preview-04-2026`` (más exhaustivo). Override: ``GEMINI_AGENT_DEEP_RESEARCH``."""
    return os.environ.get('GEMINI_AGENT_DEEP_RESEARCH') or 'deep-research-max-preview-04-2026'


def _get_deep_research_collaborative_planning() -> bool:
    """
    Reservado para compatibilidad. El bucle de dos fases (plan aprobado en servidor) usa
    :func:`_get_auto_collab_loop`; si está desactivado, el informe usa un solo ``create`` con
    ``collaborative_planning=False`` para evitar ``requires_action`` sin segundo turno.
    """
    raw = os.environ.get('GEMINI_DEEP_RESEARCH_COLLABORATIVE_PLANNING')
    if raw is None or str(raw).strip() == '':
        return False
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _get_auto_collab_loop() -> bool:
    """
    Si es True (por defecto): plan colaborativo en primer ``interactions.create`` (collaborative_planning=True);
    a continuación, segundo ``create`` con ``previous_interaction_id`` y ``collaborative_planning=False``
    para aprobar el plan y ejecutar la investigación (sin intervención del usuario). Override:
    ``GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP=0`` o ``false``.
    """
    raw = os.environ.get('GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP')
    if raw is None or str(raw).strip() == '':
        return True
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


# Segundo turno: mensaje de aprobación (documentación Google Deep Research — paso 3 "Approve and execute")
DEEP_RESEARCH_APPROVE_INPUT = (
    'El plan propuesto es adecuado. Apruebo el plan tal como está. '
    'Procede a ejecutar en profundidad la investigación y entrega el informe final completo en español (España) '
    'en Markdown, siguiendo el briefing, el plan acordado y las reglas de formato indicadas al inicio.'
)


def _report_substep_rows(single_shot: bool) -> list:
    """Tres subpasos lógicos (plan → validar → informe) para la UI. ``single_shot`` omite plan/validación."""
    ag = _get_agent_deep_research()
    if single_shot:
        return [
            {
                'id': 'plan',
                'title': 'Plan colaborativo (modo directo)',
                'status': 'skipped',
                'model': None,
                'error': None,
            },
            {
                'id': 'validate',
                'title': 'Confirmación de plan (modo directo)',
                'status': 'skipped',
                'model': None,
                'error': None,
            },
            {
                'id': 'report',
                'title': 'Generando informe (Deep Research)',
                'status': 'loading',
                'model': ag,
                'error': None,
            },
        ]
    return [
        {
            'id': 'plan',
            'title': 'Generando plan de investigación',
            'status': 'loading',
            'model': ag,
            'error': None,
        },
        {
            'id': 'validate',
            'title': 'Validando y confirmando plan (automático)',
            'status': 'pending',
            'model': None,
            'error': None,
        },
        {
            'id': 'report',
            'title': 'Generando informe (Deep Research)',
            'status': 'pending',
            'model': ag,
            'error': None,
        },
    ]


def new_report_stages_progress_state() -> dict:
    """
    Progreso en la pestaña de informes para la generación **solo del informe** (3 subpasos o 1 vía modo directo).
    Se guarda en ``company_reports.audio_progress_json`` con ``report_stages: true``.
    """
    return {
        'report_stages': True,
        'full_pipeline': False,
        'caption': (
            'Investigación en segundo plano: fases de plan (colaborativo), confirmación automática e informe. '
            'Puedes salir; el estado se actualizará al volver.'
        ),
        'steps': _report_substep_rows(not _get_auto_collab_loop()),
    }


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


def _get_output_attr(block: Any, name: str, default=None):
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


def _norm_output_type(block: Any) -> str:
    t = _get_output_attr(block, 'type')
    if t is not None and hasattr(t, 'value'):
        t = t.value
    return str(t or '').strip().lower()


def _parse_data_url_if_present(s: str) -> tuple[Optional[str], Optional[str]]:
    """Si ``s`` es data URL, devuelve (payload_base64, mime); si no, (None, None)."""
    s = (s or '').strip()
    if not s.startswith('data:'):
        return None, None
    m = re.match(r'data:([^;]+);base64,(.+)', s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(2).strip(), m.group(1).strip()
    return None, None


def _bytes_to_b64(data: Any) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        if not data:
            return None
        return base64.b64encode(bytes(data)).decode('ascii')
    s = str(data).strip()
    if not s:
        return None
    b64, _mime = _parse_data_url_if_present(s)
    if b64:
        return b64
    return s


# Límite defensivo (~12M chars base64 ≈ ~9 MiB binario) para no inflar TEXT en BD por error.
_GEMINI_REPORT_MAX_B64_IMAGE_CHARS = int(
    os.environ.get('GEMINI_REPORT_MAX_B64_IMAGE_CHARS') or 12_000_000
)


def _image_block_to_markdown(block: Any, index: int) -> Optional[str]:
    """
    Convierte un bloque de salida tipo imagen (base64 en API Interactions) en una línea Markdown
    con data URI, visible en web y en correo (HTML generado desde Markdown).
    """
    mime = _get_output_attr(block, 'mime_type') or 'image/png'
    raw = _get_output_attr(block, 'data')
    if raw is None:
        inline = _get_output_attr(block, 'inline_data')
        if inline is not None:
            raw = _get_output_attr(inline, 'data')
            mime = _get_output_attr(inline, 'mime_type') or mime
    b64 = _bytes_to_b64(raw)
    if not b64:
        logger.warning('Bloque de imagen en outputs sin datos base64 (índice %s)', index)
        return None
    if len(b64) > _GEMINI_REPORT_MAX_B64_IMAGE_CHARS:
        logger.warning(
            'Imagen de informe omitida por tamaño (base64 > %s chars)',
            _GEMINI_REPORT_MAX_B64_IMAGE_CHARS,
        )
        return (
            f'*[Imagen del informe omitida por tamaño; ajusta GEMINI_REPORT_MAX_B64_IMAGE_CHARS]*'
        )
    safe_mime = mime if isinstance(mime, str) and mime.startswith('image/') else 'image/png'
    return f'![Figura {index}](data:{safe_mime};base64,{b64})'


def _extract_interaction_text(interaction) -> str:
    """
    Reconstruye el informe: texto e imágenes de ``interaction.outputs`` en orden.
    El agente Deep Research puede devolver imágenes (p. ej. gráficos) como bloques separados;
    se incrustan como ``data:image/...;base64,...`` en Markdown.
    """
    outputs = getattr(interaction, 'outputs', None) or []
    parts = []
    img_n = 0
    for block in outputs:
        otype = _norm_output_type(block)
        if otype == 'image' or otype in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
            img_n += 1
            md = _image_block_to_markdown(block, img_n)
            if md:
                parts.append(md)
            continue
        inline = _get_output_attr(block, 'inline_data')
        if inline is not None and _get_output_attr(inline, 'data'):
            img_n += 1
            md = _image_block_to_markdown(block, img_n)
            if md:
                parts.append(md)
            continue
        if not otype or otype in ('text', 'output'):
            t = _get_output_attr(block, 'text')
            if t and str(t).strip():
                parts.append(str(t).strip())
            continue
        t = _get_output_attr(block, 'text')
        if t and str(t).strip():
            parts.append(str(t).strip())
        else:
            logger.debug('Bloque de salida sin texto ni imagen utilizable: type=%s', otype)
    return '\n\n'.join(parts).strip() if parts else ''


def _interaction_status_str(raw) -> str:
    s = raw or 'unknown'
    if isinstance(s, str):
        return s.lower()
    return str(getattr(s, 'value', s)).lower()


def _emit_report_substeps(
    on_report_substeps: Optional[Callable[[list], None]], sts: list,
) -> None:
    if on_report_substeps:
        on_report_substeps([dict(s) for s in sts])


def _interactions_create_deep_research(
    client, *, input_text: str, agent_name: str, collab: bool, previous_interaction_id: Optional[str] = None
) -> Any:
    agent_config = {
        'type': 'deep-research',
        'visualization': 'auto',
        'thinking_summaries': 'auto',
        'collaborative_planning': collab,
    }
    last_create_err: Optional[Exception] = None
    for with_agent_cfg in (True, False):
        try:
            kwargs: dict = {
                'input': input_text,
                'agent': agent_name,
                'background': True,
                'store': True,
            }
            if with_agent_cfg:
                kwargs['agent_config'] = agent_config
            if previous_interaction_id:
                kwargs['previous_interaction_id'] = str(previous_interaction_id)[:200]
            return client.interactions.create(**kwargs)
        except Exception as ex:
            last_create_err = ex
            if with_agent_cfg:
                logger.warning('interactions.create (Deep Research) reintento sin agent_config: %s', ex)
                continue
            raise
    if last_create_err:
        raise last_create_err
    raise GeminiServiceError('interactions.create devolvió vacío')


def _poll_interaction_once(
    client, interaction_id: str, on_status_update, poll_n: int, last_logged: Optional[str]
) -> tuple:
    inter = client.interactions.get(interaction_id)
    status = _interaction_status_str(getattr(inter, 'status', None))
    if status != last_logged or poll_n % 8 == 0:
        logger.info('Deep Research poll: id=%s status=%s', interaction_id, status)
    return inter, status


def _poll_interaction_block(
    client,
    interaction_id: str,
    deadline: float,
    poll_interval_seconds: int,
    on_status_update,
    phase_msg: str,
) -> tuple[str, Any]:
    """
    Devuelve (``completed`` | ``failed`` | ``timeout`` | ``cancelled`` | ``requires_action``, carga útil).
    En ``failed``/``timeout``/``cancelled`` la carga es str; en los demás es el objeto interacción.
    """
    poll_n = 0
    last_logged: Optional[str] = None
    while time.monotonic() < deadline:
        inter, status = _poll_interaction_once(
            client, interaction_id, on_status_update, poll_n, last_logged
        )
        last_logged = status
        poll_n += 1
        if status == 'completed':
            return 'completed', inter
        if status == 'failed':
            em = getattr(inter, 'error', 'Error desconocido') or 'Error desconocido'
            if hasattr(em, 'message'):
                em = em.message
            return 'failed', str(em)
        if status in ('cancelled', 'canceled'):
            return 'cancelled', 'La interacción fue cancelada en el servicio de Gemini.'
        if status == 'requires_action':
            return 'requires_action', inter
        if status not in ('in_progress', 'pending', 'running', 'unknown', 'active'):
            logger.warning('Deep Research: estado inesperado %s, sigo haciendo poll', status)
        time.sleep(poll_interval_seconds)
        if on_status_update:
            on_status_update('processing', f'{phase_msg} (estado: {status})')
    return 'timeout', (
        f'Tiempo de espera con la API aún en curso. interaction_id={interaction_id}. '
        f'Puedes reintentar o usar GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP=0 para un solo paso (sin fase de plan).'
    )


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
    on_report_substeps: Optional[Callable[[list], None]] = None,
) -> Tuple[str, str]:
    """
    Informe Deep Research: modo **dos fases** (por defecto) con plan colaborativo y confirmación
    automática vía ``previous_interaction_id``, o un solo ``create`` si
    ``GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP=0``.

    ``on_report_substeps`` recibe 3 diccionarios (plan / validar / informe) con ``status``:
    ``loading`` | ``ok`` | ``error`` | ``pending`` | ``skipped``.
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

    prompt = f"""Actúa como un **Analista Senior de Equity Research** con enfoque en diseño editorial profesional.

**Empresa y contexto de investigación**
- Empresa: **{name}**
- Símbolo: {symbol or 'N/A'} | ISIN: {isin or 'N/A'}

**Briefing (prioridad y alcance)**
{description}
{points_text}

**REGLAS DE FORMATO VISUAL**
- Estructura amigable: no escribas párrafos de más de unas **cuatro líneas** al visualizarlos; divide el texto. Usa **negritas** para resaltar hallazgos, no solo títulos.
- Bloques de resaltado: incluye al inicio un **Resumen ejecutivo (Executive summary)** y, al inicio de **cada sección principal**, un bloque **Key takeaways**; en ambos casos encierra el contenido en **bloques de cita** Markdown: cada línea del bloque debe comenzar con el carácter **>** (cita) para que destaquen en web y correo.
- Tablas **condicionales:** usa tablas Markdown solo si los datos son **relevantes y están** en las fuentes. Si faltan datos, usa **listas** (puedes añadir un **icono/emoji** al inicio de viñetas, p. ej. 📈 📊 ✓) en lugar de tablas vacías o genéricas.
- **Visualización:** para gráficos o infografías, usa la **herramienta nativa** del agente (``visualization: auto`` en el backend). **No** generes Mermaid, xychart-beta, ASCII-art sustitutivo de gráficos ni bloques de código con pseudo-diagramas: el lector no los renderizará.
- **PROPORCIÓN VISUAL CRÍTICA:** al generar gráficos e infografías mediante ``visualization: auto``, utiliza un estilo de **tipografía minimalista y profesional**. El tamaño de las fuentes dentro de la imagen no debe ser dominante; títulos y etiquetas deben tener un **peso visual equivalente** al texto del informe para mantener la **armonía estética** (evita gráficos que parezcan carteles con texto gigante frente al cuerpo del informe).
- Título con **H1**; secciones con **H2** y **H3** de forma clara y jerarquizada.

**RIGOR, CITAS Y DATOS**
- **Prohibido** el rellano genérico. Cada **dato numérico** relevante debe ir acompañado de una cita en texto con el formato **`[cite: X]`** (documento, CNMV, informe, prensa verificable, etc.) cuando exista. No inventes la cita.
- **Protocolo de datos faltantes:** si una métrica (EBITDA, PER actual, márgenes, deuda, guidance, etc.) **no aparece** en las fuentes, declara **«Dato no disponible»** y explica en una frase breve el motivo. **Prohibido** estimar, interpolar o inventar sin base.
- Prioriza análisis accionable; contrapón oportunidad y riesgo.

**CODIFICACIÓN Y ENTREGA**
- Responde en **español (España)**. Salida en texto **UTF-8** con tildes y eñes correctas en el carácter; **no** uses secuencias escapadas tipo ``\\u00f3``.

**BIBLIOGRAFÍA / FUENTES**
- Al final, crea la sección **Fuentes consultadas** (o **Fuentes consultadas y bibliografía**) con hipervínculos descriptivos: ``[Nombre de la fuente](URL)`` cuando haya enlace; si no, solo el nombre y la cita asociada.

**Entrega final** en **Markdown** avanzado, legible en **web y correo**."""

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        agent_name = _get_agent_deep_research()
        auto_loop = _get_auto_collab_loop()
        single_shot = not auto_loop
        deadline = time.monotonic() + max_wait_seconds
        sts = _report_substep_rows(single_shot)
        if on_status_update:
            on_status_update('processing', 'Iniciando investigación...')
        _emit_report_substeps(on_report_substeps, sts)

        def _fail_substeps(phase: str, err: str) -> None:
            e = (err or 'Error')[:4000]
            if phase == 'plan':
                sts[0]['status'] = 'error'
                sts[0]['error'] = e
            elif phase == 'validate':
                sts[1]['status'] = 'error'
                sts[1]['error'] = e
            else:
                sts[2]['status'] = 'error'
                sts[2]['error'] = e
            _emit_report_substeps(on_report_substeps, sts)

        if not auto_loop:
            # Un solo create; sin fase de plan (evita requires_action)
            try:
                interaction = _interactions_create_deep_research(
                    client,
                    input_text=prompt,
                    agent_name=agent_name,
                    collab=False,
                    previous_interaction_id=None,
                )
            except Exception as ex:
                _fail_substeps('report', str(ex))
                if on_status_update:
                    on_status_update('failed', str(ex))
                return ('failed', str(ex))
            iid = interaction.id if hasattr(interaction, 'id') else str(interaction)
            logger.info('Deep Research (modo directo): agent=%s interaction_id=%s', agent_name, iid)
            if on_interaction_created:
                try:
                    on_interaction_created(str(iid)[:100])
                except Exception as cb_err:
                    logger.warning('on_interaction_created falló: %s', cb_err)
            if on_status_update:
                on_status_update('processing', 'Investigando en segundo plano (modo directo)…')
            res, data = _poll_interaction_block(
                client, iid, deadline, poll_interval_seconds, on_status_update, 'Generando informe',
            )
            if res in ('failed', 'timeout', 'cancelled'):
                msg = str(data)
                if res == 'timeout':
                    msg = str(data) if data else 'Timeout'
                _fail_substeps('report', msg)
                if on_status_update:
                    on_status_update('failed', msg)
                return ('failed', msg)
            if res == 'requires_action':
                m = 'La API devolvió requires_action en modo directo. Prueba a activar el bucle automático (GEMINI_DEEP_RESEARCH_AUTO_COLLAB_LOOP=1) o otro agente.'
                _fail_substeps('report', m)
                if on_status_update:
                    on_status_update('failed', m)
                return ('failed', m)
            inter = data
            text = _extract_interaction_text(inter) or 'Informe vacío'
            sts[2]['status'] = 'ok'
            sts[2]['error'] = None
            _emit_report_substeps(on_report_substeps, sts)
            if on_status_update:
                on_status_update('completed', 'Informe completado')
            return ('completed', text)

        # Bucle de dos fases: plan (collab) → aprobación automática (sin collab) → informe
        if on_status_update:
            on_status_update('processing', 'Fase 1: generando plan de investigación…')
        try:
            p1 = _interactions_create_deep_research(
                client, input_text=prompt, agent_name=agent_name, collab=True, previous_interaction_id=None
            )
        except Exception as ex:
            _fail_substeps('plan', str(ex))
            if on_status_update:
                on_status_update('failed', str(ex))
            return ('failed', str(ex))
        id1 = p1.id if hasattr(p1, 'id') else str(p1)
        logger.info('Deep Research fase 1 (plan): agent=%s interaction_id=%s', agent_name, id1)

        r1, d1 = _poll_interaction_block(
            client, str(id1), deadline, poll_interval_seconds, on_status_update, 'Generando plan de investigación',
        )
        if r1 in ('failed', 'timeout', 'cancelled'):
            msg = d1 if isinstance(d1, str) else str(d1)
            if r1 == 'timeout' and not isinstance(d1, str):
                msg = str(d1)
            _fail_substeps('plan', msg)
            if on_status_update:
                on_status_update('failed', msg)
            return ('failed', msg)
        if r1 not in ('completed', 'requires_action'):
            msg = f'Estado inesperado en fase 1: {r1}'
            _fail_substeps('plan', msg)
            return ('failed', msg)
        # Plan listo; preparar aprobación automática
        sts[0]['status'] = 'ok'
        sts[0]['error'] = None
        sts[1]['status'] = 'loading'
        sts[1]['error'] = None
        _emit_report_substeps(on_report_substeps, sts)
        if on_status_update:
            on_status_update('processing', 'Validando y confirmando plan (automático)…')
        try:
            p2 = _interactions_create_deep_research(
                client,
                input_text=DEEP_RESEARCH_APPROVE_INPUT,
                agent_name=agent_name,
                collab=False,
                previous_interaction_id=str(id1)[:200],
            )
        except Exception as ex:
            _fail_substeps('validate', str(ex))
            if on_status_update:
                on_status_update('failed', str(ex))
            return ('failed', str(ex))
        id2 = p2.id if hasattr(p2, 'id') else str(p2)
        logger.info('Deep Research fase 2 (informe): agent=%s interaction_id=%s', agent_name, id2)
        if on_interaction_created:
            try:
                on_interaction_created(str(id2)[:100])
            except Exception as cb_err:
                logger.warning('on_interaction_created falló: %s', cb_err)
        sts[1]['status'] = 'ok'
        sts[1]['error'] = None
        sts[2]['status'] = 'loading'
        sts[2]['error'] = None
        _emit_report_substeps(on_report_substeps, sts)
        if on_status_update:
            on_status_update('processing', 'Generando informe en profundidad…')

        r2, d2 = _poll_interaction_block(
            client, str(id2), deadline, poll_interval_seconds, on_status_update, 'Generando informe',
        )
        if r2 in ('failed', 'timeout', 'cancelled'):
            msg = d2 if isinstance(d2, str) else str(d2)
            if r2 == 'timeout' and not isinstance(d2, str):
                msg = str(d2)
            _fail_substeps('report', msg)
            if on_status_update:
                on_status_update('failed', msg)
            return ('failed', msg)
        if r2 == 'requires_action':
            m = 'La fase 2 quedó en requires_action. Revisa el agente o inténtalo de nuevo.'
            _fail_substeps('report', m)
            if on_status_update:
                on_status_update('failed', m)
            return ('failed', m)
        if r2 != 'completed':
            m = f'Estado inesperado en fase 2: {r2}'
            _fail_substeps('report', m)
            return ('failed', m)
        inter2 = d2
        text = _extract_interaction_text(inter2) or 'Informe vacío'
        sts[2]['status'] = 'ok'
        sts[2]['error'] = None
        _emit_report_substeps(on_report_substeps, sts)
        if on_status_update:
            on_status_update('completed', 'Informe completado')
        return ('completed', text)

    except ImportError as e:
        raise GeminiServiceError(f'Paquete google-genai no instalado: {e}')
    except GeminiServiceError:
        raise
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

# Prompt maestro (estructura de diálogo tipo audios estilo NotebookLM / guion conversacional)
PODCAST_SCRIPT_PROMPT = f"""Eres guionista de diálogos de inversión. Convierte el informe de Deep Research adjunto en una conversación **solo entre {PODCAST_SPEAKER_1}** (hombre, voz informativa) y **{PODCAST_SPEAKER_2}** (mujer, voz clara/curiosa).

**REGLAS DE ORO DE DURACIÓN (presupuesto de palabras):**
1. **Límite estricto:** el guion debe situarse en **{PODCAST_SCRIPT_TARGET_MIN}–{PODCAST_SCRIPT_TARGET_MAX} palabras**. **Nunca** superes **{PODCAST_HARD_MAX_WORDS}** palabras.
2. **Ritmo (~150 wpm en español):** ~**900** palabras ≈ **6 minutos**. No escribas de más asumiendo un recorte después.
3. **Tres actos (orientación):** Intro ~{PODCAST_ACT1_WORDS_GUIDE} p. / Cuerpo ~{PODCAST_ACT2_WORDS_GUIDE} p. (solo **3** hallazgos) / Cierre ~{PODCAST_ACT3_WORDS_GUIDE} p.

**ESTRUCTURA DE DIÁLOGO (obligatoria):**
- **Apertura informal:** el primer turno debe ser un saludo natural entre los dos, p. ej. «Hola {PODCAST_SPEAKER_2}, estuve viendo estos datos de…» (sin nombre de programa ni «bienvenidos»).
- **Dinámica:** alterna frases **cortas y contundentes** de {PODCAST_SPEAKER_2} (preguntas, reacciones) con **explicaciones algo más largas** de {PODCAST_SPEAKER_1} (datos, contexto). Evita monólogos de un solo hablante.
- **Muletillas de acuerdo (espaciadas):** incluye a menudo, de forma orgánica, interjecciones como *Exacto*, *Justo eso*, *Totalmente* o *Mira esto* (o variantes en castellano de España) para mantener el ritmo; no las repitas en bucle en cada frase.
- **Sin audiencia:** la conversación es **únicamente entre {PODCAST_SPEAKER_1} y {PODCAST_SPEAKER_2}**. Prohibido: «gracias por escucharnos», «bienvenidos al programa», «ustedes», o dirigirse a oyentes. No inventes título de emisora.
- **Cierre (últimas réplicas):** termina con una **reflexión breve o pregunta final de {PODCAST_SPEAKER_2}**; **{PODCAST_SPEAKER_1}** responde con **una sola frase de menos de 5 palabras** (cierre técnicamente seco, sin despedida emotiva a la audiencia). No despedidas de radio (ni «hasta la próxima semana en…»).
- **Registro:** español de **España (peninsular)**, analítico, para inversor.

**ETIQUETAS DE DIRECCIÓN (TTS) — inclúyelas en el cuerpo del guion donde tenga sentido (no en todas las frases):**
- **[uhm]:** a veces **antes** de que {PODCAST_SPEAKER_2} lance la pregunta “difícil” o el dato clave, para sonar humano.
- **[laughs]:** a veces **después** de una analogía breve o un comentario ligeramente irónico.
- **[short pause]:** tras una **cifra o ratio importante** (p. ej. un PER, un márgen) o al cambiar de sub-tema. **Nunca** [long pause] ni silencios largos.

**REGLAS DE ESTILO (interfaz TTS):**
- Prefijos exactos de línea: **{PODCAST_SPEAKER_1}:** y **{PODCAST_SPEAKER_2}:** (una intervención por línea).
- **Priorización del cuerpo:** solo 3 ideas fuertes del informe; no listes todo el deep research.

**Formato de salida:** **solo** el guion (una réplica por línea), sin markdown, sin título de documento y sin notas al lector."""


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
2. Mantén el **cierre final** (pregunta o reflexión de Taylor + respuesta muy breve de Álex, **menos de 5 palabras**), sin despedidas a audiencia ni nombre de programa.
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


def _pcm_from_tts_response(response) -> bytes:
    """Extrae PCM crudo (s16le mono 24 kHz) de una respuesta generate_content con modalidad AUDIO."""
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
    mime = (getattr(inline, 'mime_type', None) or '').lower()
    if not data:
        raise GeminiServiceError('No hay datos de audio en la respuesta')
    raw: bytes
    if isinstance(data, str):
        raw = base64.b64decode(data)
    else:
        raw = data
    if 'mpeg' in mime or 'mp3' in mime:
        raise GeminiServiceError(
            'La API devolvió MP3; esta integración espera PCM lineal para escribir WAV. '
            'Actualiza google-genai o contacta soporte si el modelo deja de enviar PCM.'
        )
    return raw


def _synthesize_multispeaker_podcast_wav(client, script: str, output_path: str) -> None:
    """
    TTS multispeaker con ``gemini-3.1-flash-tts-preview``.
    Temperatura de **síntesis de audio** con ``GEMINI_TTS_TEMPERATURE`` (por defecto 0,65), no la del guion.
    Salida: WAV PCM 24 kHz mono (formato documentado en ai.google.dev para TTS).
    """
    import wave
    from google.genai import types

    tts_user = f"""**Director de audio (no leer en voz alta):** Accent: Peninsular Spanish from Spain. Neutral, professional; avoid Latin American inflections.

This is a private two-person conversation in European Spanish; there is no live audience, show title, or sign-off to listeners. Speak the dialogue naturally.

Speakers and voices:
- {PODCAST_SPEAKER_1}: male, Charon, informative, slightly longer lines with figures.
- {PODCAST_SPEAKER_2}: female, Kore, firm, short punchy questions and reactions.

Respect [bracket tags] such as [short pause], [uhm], [laughs], [sigh] — keep them short; never stretch silence unnaturally on long monologues.

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
            temperature=_get_tts_synthesis_temperature(),
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
    logger.info(
        'Audio podcast multi-locutor guardado: %s (bytes_pcm=%s, tts_temp=%s)',
        output_path,
        len(all_pcm),
        _get_tts_synthesis_temperature(),
    )


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
    Progreso unificado: subpasos del informe (plan / validación / informe) + guion + TTS + correo.
    Se persiste en ``company_reports.audio_progress_json`` con ``full_pipeline: true``.
    """
    first = _report_substep_rows(not _get_auto_collab_loop())
    return {
        'full_pipeline': True,
        'report_stages': False,
        'caption': (
            'Proceso completo en segundo plano: plan e informe Deep Research, audio (es-ES) y envío por correo. '
            'Puedes salir; recibirás el informe y el audio en tu email.'
        ),
        'steps': first
        + [
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
    """Incorpora guion + TTS en los índices 3 y 4 del pipeline completo (tras los 3 subpasos del informe)."""
    out = {**full_state, 'full_pipeline': True}
    steps = [dict(s) for s in (out.get('steps') or [])]
    tts_steps = (tts_progress or {}).get('steps') or []
    if len(steps) >= 5 and len(tts_steps) >= 1:
        for k in ('status', 'error', 'model'):
            if k in tts_steps[0] and tts_steps[0][k] is not None:
                steps[3][k] = tts_steps[0][k]
    if len(steps) >= 6 and len(tts_steps) >= 2:
        for k in ('status', 'error', 'model'):
            if k in tts_steps[1] and tts_steps[1][k] is not None:
                steps[4][k] = tts_steps[1][k]
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
       **Kore (Taylor)**, ``response_modalities=['AUDIO']``, temperatura de **audio**
       (``GEMINI_TTS_TEMPERATURE``, predeterminado 0,65), PCM 24 kHz mono → WAV según la guía
       pública de TTS (el producto «Podcasts»/NotebookLM en la app de Google usa otro canal).

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
