"""PDF experimental desde Markdown de informes (reportlab, sin dependencias nativas cairo)."""
from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


def markdown_report_to_pdf_bytes(full_md: str) -> Optional[bytes]:
    """
    Convierte Markdown a PDF con texto fluido (tablas/imágenes complejas pueden simplificarse).
    Sin cairo/pango: apto para VM mínima.
    """
    try:
        import markdown as md_lib
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from xml.sax.saxutils import escape

        md = full_md or ''
        html = md_lib.markdown(md, extensions=['extra', 'nl2br', 'tables'])
        text = re.sub(r'<[^>]+>', '\n', html)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if not text:
            text = '(Informe vacío)'

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
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
        story = []
        for block in text.split('\n\n'):
            chunk = (block or '').strip()
            if not chunk:
                continue
            safe = escape(chunk).replace('\n', '<br/>')
            story.append(Paragraph(safe, body_style))
            story.append(Spacer(1, 4))

        doc.build(story)
        data = buf.getvalue()
        return data if data else None
    except Exception as e:
        logger.warning('markdown_report_to_pdf_bytes: %s', e)
        return None
