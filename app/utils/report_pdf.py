"""PDF desde Markdown de informes (reportlab + figuras data URI embebidas)."""
from __future__ import annotations

import base64
import logging
import re
from io import BytesIO
from typing import List, Optional

logger = logging.getLogger(__name__)

# ![alt](data:image/...;base64,...) — una línea típica de los informes Gemini
_MD_IMG_LINE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)', re.MULTILINE)

_DATA_URI_RE = re.compile(
    r'^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$',
    re.DOTALL | re.IGNORECASE,
)


def _data_uri_to_bytes(uri: str) -> Optional[bytes]:
    u = (uri or '').strip()
    m = _DATA_URI_RE.match(u.replace('\n', '').replace('\r', ''))
    if not m:
        return None
    try:
        return base64.b64decode(m.group(2), validate=False)
    except Exception:
        return None


def _append_markdown_text_story(
    story: List,
    md_fragment: str,
    body_style,
    escape,
    md_lib,
) -> None:
    frag = (md_fragment or '').strip()
    if not frag:
        return
    html = md_lib.markdown(frag, extensions=['extra', 'nl2br', 'tables'])
    plain = re.sub(r'<[^>]+>', '\n', html)
    plain = re.sub(r'\n{3,}', '\n\n', plain).strip()
    if not plain:
        return
    from reportlab.platypus import Paragraph, Spacer

    for block in plain.split('\n\n'):
        chunk = (block or '').strip()
        if not chunk:
            continue
        safe = escape(chunk).replace('\n', '<br/>')
        story.append(Paragraph(safe, body_style))
        story.append(Spacer(1, 4))


def _make_flowable_image(raw: bytes, content_width_pt: float):
    """Inserta imagen raster escalada al ancho útil de página."""
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage

    try:
        from PIL import Image as PILImage

        im = PILImage.open(BytesIO(raw))
        im.load()
        w_px, h_px = im.size
    except Exception:
        try:
            ir = ImageReader(BytesIO(raw))
            w_px, h_px = ir.getSize()
        except Exception:
            w_px, h_px = 600, 400

    scale = content_width_pt / float(w_px or 1)
    width_pt = content_width_pt
    height_pt = h_px * scale
    max_h = 620.0
    if height_pt > max_h:
        scale2 = max_h / height_pt
        height_pt *= scale2
        width_pt *= scale2

    return RLImage(ImageReader(BytesIO(raw)), width=width_pt, height=height_pt)


def markdown_report_to_pdf_bytes(full_md: str) -> Optional[bytes]:
    """
    PDF con texto (Markdown→HTML→texto) e **imágenes embebidas** tipo data URI en líneas ``![](...)``.
    URLs http(s) sin datos binarios no se descargan (solo nota).
    """
    try:
        import markdown as md_lib
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from xml.sax.saxutils import escape

        md = full_md or ''
        margin_side_pt = 18 * 72 / 25.4
        margin_tb_pt = 16 * 72 / 25.4
        content_width_pt = float(A4[0]) - 2 * margin_side_pt

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=margin_side_pt,
            rightMargin=margin_side_pt,
            topMargin=margin_tb_pt,
            bottomMargin=margin_tb_pt,
        )
        base = getSampleStyleSheet()
        body_style = ParagraphStyle(
            name='ReportBody',
            parent=base['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=13,
            spaceAfter=6,
        )

        story: List = []

        def flush_text(fragment: str) -> None:
            _append_markdown_text_story(story, fragment, body_style, escape, md_lib)

        pos = 0
        for m in _MD_IMG_LINE.finditer(md):
            before = md[pos : m.start()]
            flush_text(before)
            url = (m.group(1) or '').strip()
            raw = _data_uri_to_bytes(url)
            if raw:
                try:
                    story.append(_make_flowable_image(raw, content_width_pt))
                    story.append(Spacer(1, 8))
                except Exception as img_e:
                    logger.warning('PDF imagen omitida: %s', img_e)
                    story.append(
                        Paragraph(escape('[Figura: error al rasterizar en PDF]'), body_style)
                    )
                    story.append(Spacer(1, 4))
            else:
                if url.startswith(('http://', 'https://')):
                    note = f'<i>[Ilustración externa: {escape(url[:120])}{"…" if len(url) > 120 else ""}]</i>'
                else:
                    note = '<i>[Figura no embebida en PDF]</i>'
                story.append(Paragraph(note, body_style))
                story.append(Spacer(1, 4))
            pos = m.end()

        tail = md[pos:]
        flush_text(tail)

        if not story:
            story.append(Paragraph(escape('(Informe vacío)'), body_style))

        doc.build(story)
        data = buf.getvalue()
        return data if data else None
    except Exception as e:
        logger.warning('markdown_report_to_pdf_bytes: %s', e)
        return None
