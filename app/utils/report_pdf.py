"""PDF experimental desde Markdown de informes (xhtml2pdf)."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def markdown_report_to_pdf_bytes(full_md: str) -> Optional[bytes]:
    """Devuelve PDF en bytes o None si falla la conversión."""
    try:
        from io import BytesIO

        import markdown as md_lib
        from xhtml2pdf import pisa

        md = full_md or ''
        html_body = md_lib.markdown(md, extensions=['extra', 'nl2br', 'tables'])
        wrapper = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>
@page {{ size: A4; margin: 18mm; }}
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #1e293b; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 9pt; }}
th, td {{ border: 1px solid #cbd5e1; padding: 5px 7px; text-align: left; }}
th {{ background: #0f766e; color: white; }}
img {{ max-width: 100%; height: auto; }}
blockquote {{ border-left: 4px solid #0d9488; margin: 0.8em 0; padding: 0.4em 0.8em; background: #f8fafc; }}
h1, h2, h3 {{ color: #0f172a; }}
pre {{ white-space: pre-wrap; font-size: 8pt; }}
</style></head><body>{html_body}</body></html>"""
        buf = BytesIO()
        result = pisa.CreatePDF(src=wrapper.encode('utf-8'), dest=buf, encoding='utf-8')
        if getattr(result, 'err', 0):
            logger.warning('xhtml2pdf devolvió err=%s', getattr(result, 'err', None))
            return None
        data = buf.getvalue()
        return data if data else None
    except Exception as e:
        logger.warning('markdown_report_to_pdf_bytes: %s', e)
        return None
