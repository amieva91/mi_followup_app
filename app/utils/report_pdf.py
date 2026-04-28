"""PDF del informe: mismo aspecto que la web (Markdown→HTML + CSS + Chromium)."""
from __future__ import annotations

import html as html_module
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Coherente con app/templates/portfolio/asset_detail.html (.report-markdown.report-content)
_REPORT_MARKDOWN_CSS = """
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  margin: 0;
  padding: 0;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, "Noto Sans", sans-serif,
    "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
  background: #f9fafb;
  color: #1e293b;
}
.pdf-meta {
  margin-bottom: 1.5rem;
  padding: 1rem 1.25rem 1.25rem;
  background: linear-gradient(145deg, rgba(248,251,252,0.96), rgba(241,247,248,0.9));
  border: 1px solid rgba(63, 95, 115, 0.13);
  border-radius: 12px;
}
.pdf-meta h1 {
  font-size: clamp(1.4rem, 3vw, 1.85rem);
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.35rem 0;
  line-height: 1.25;
}
.pdf-meta p {
  margin: 0;
  color: #475569;
  font-size: 1rem;
}
.prose { max-width: none; }
.report-markdown h1, .report-markdown h2, .report-markdown h3, .report-markdown h4 {
    font-weight: 700;
    margin-top: 1.25em;
    margin-bottom: 0.5em;
    line-height: 1.3;
    color: #0f172a;
}
.report-markdown h1 { font-size: 1.5rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.25em; }
.report-markdown h2 { font-size: 1.25rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.2em; }
.report-markdown h3, .report-markdown h4 { font-size: 1.1rem; }
.report-markdown p { margin-bottom: 0.75em; line-height: 1.7; color: #374151; }
.report-markdown ul, .report-markdown ol {
    margin: 0.5em 0 1em 1.25em;
    padding-left: 1em;
}
.report-markdown li { margin-bottom: 0.35em; line-height: 1.6; }
.report-markdown strong { color: #111827; font-weight: 600; }
.report-markdown table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.9rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border-radius: 8px;
    overflow: hidden;
}
.report-markdown th, .report-markdown td {
    border: 1px solid #e5e7eb;
    padding: 0.6em 0.75em;
    text-align: left;
}
.report-markdown th {
    background: #0f766e;
    color: white;
    font-weight: 600;
}
.report-markdown tr:nth-child(even) { background: #f9fafb; }
.report-markdown tr:hover { background: #f3f4f6; }
.report-markdown blockquote {
    border-left: 4px solid #0d9488;
    margin: 1em 0;
    padding: 0.5em 1em;
    background: rgba(240, 253, 250, 0.55);
    color: #334155;
    font-style: italic;
}
.report-markdown hr { border: none; border-top: 1px solid #e5e7eb; margin: 1.5em 0; }
.report-markdown code {
    background: #f3f4f6;
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.9em;
}
.report-markdown pre {
    background: #f3f4f6;
    padding: 0.85rem 1rem;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 0.88rem;
}
.report-markdown.report-content {
    font-size: 1.15rem !important;
    line-height: 1.8;
    color: #1e293b;
}
.report-markdown.report-content p {
    color: #334155;
    margin-bottom: 0.85em;
}
.report-markdown.report-content blockquote {
    font-size: 1.08rem;
    line-height: 1.75;
    padding: 1.35rem 1.6rem;
    margin: 2rem 0;
    background: linear-gradient(165deg, rgba(248, 250, 252, 0.98) 0%, rgba(240, 253, 250, 0.42) 55%, rgba(241, 245, 249, 0.5) 100%);
    border-left: 5px solid #0d9488;
    border-radius: 0 12px 12px 0;
    color: #334155;
    font-style: italic;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}
.report-markdown.report-content h1 {
    font-size: clamp(1.65rem, 4vw, 2.05rem);
    margin-bottom: 1.25rem;
}
.report-markdown.report-content h2 {
    font-size: clamp(1.28rem, 3vw, 1.62rem);
    margin-top: 2rem;
}
.report-markdown.report-content img {
    max-width: 85% !important;
    height: auto;
    display: block;
    margin: 3rem auto;
    border-radius: 8px;
    border: 1px solid rgba(226, 232, 240, 0.95);
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.09);
}
.pdf-root {
  max-width: 920px;
  margin: 0 auto;
  padding: 8px 4px 24px;
}
"""


def _markdown_to_body_html(md: str) -> str:
    """Misma familia de conversiones que el cliente (marked): tablas, saltos, extras."""
    import markdown as md_lib

    raw = md_lib.markdown(
        md or '',
        extensions=[
            'extra',
            'nl2br',
            'tables',
            'sane_lists',
            'fenced_code',
        ],
    )
    return raw


def build_report_pdf_html(
    full_md: str,
    *,
    document_title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Documento HTML completo listo para Chromium (UTF-8, estilos embebidos)."""
    body_inner = _markdown_to_body_html(full_md)
    safe_title = html_module.escape(document_title or 'Informe')
    safe_sub = html_module.escape(subtitle or '') if subtitle else ''
    meta_block = ''
    if document_title or subtitle:
        meta_block = (
            f'<header class="pdf-meta">'
            f'<h1>📄 {safe_title}</h1>'
            + (f'<p>{safe_sub}</p>' if safe_sub else '')
            + '</header>'
        )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>
{_REPORT_MARKDOWN_CSS}
</style>
</head>
<body>
<div class="pdf-root">
{meta_block}
<div class="prose max-w-none report-markdown report-content">
{body_inner}
</div>
</div>
</body>
</html>
"""


def markdown_report_to_pdf_bytes(
    full_md: str,
    *,
    document_title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> Optional[bytes]:
    """
    Renderiza el informe como PDF vía Playwright/Chromium (impresión con fondos y CSS como la web).
    """
    md = full_md or ''
    if not md.strip():
        return None
    # Navegadores junto al paquete (mismo path que `PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install`).
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')
    html_doc = build_report_pdf_html(md, document_title=document_title, subtitle=subtitle)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning('markdown_report_to_pdf_bytes: Playwright no instalado')
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--font-render-hinting=none',
                ],
            )
            try:
                page = browser.new_page()
                page.set_default_timeout(180_000)
                page.set_content(html_doc, wait_until='load')
                pdf_bytes = page.pdf(
                    format='A4',
                    print_background=True,
                    margin={
                        'top': '12mm',
                        'right': '12mm',
                        'bottom': '14mm',
                        'left': '12mm',
                    },
                )
                return pdf_bytes if pdf_bytes else None
            finally:
                browser.close()
    except Exception as e:
        logger.warning('markdown_report_to_pdf_bytes: %s', e)
        return None
