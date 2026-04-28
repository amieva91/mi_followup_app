"""
Utilidades para envío de emails
"""
import base64
import re
import smtplib
from email import encoders
from email.header import Header
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, formataddr

from flask import url_for, current_app
from flask_mail import Message
from app import mail


# Regex: sustituir src=data:image/...;base64,... por cid (uso en HTML ya convertido desde Markdown)
_SRC_DATA_URI_RE = re.compile(
    r'src=(["\'])data:image/(?P<sub>[^;]+);base64,(?P<b64>[A-Za-z0-9+/=\s\r\n]+)\1',
    re.IGNORECASE | re.DOTALL,
)


_REPORT_EMAIL_SHELL_CSS = """
<style type="text/css">
body { font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
.container { max-width: 700px; margin: 0 auto; padding: 20px; }
.header { background: #1e3a8a; color: white; padding: 20px; text-align: center; }
.content { padding: 30px; background: #f9fafb; }
.report-email-body { background: white; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px; margin-top: 16px; }
.report-email-body table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9rem; }
.report-email-body th, .report-email-body td { border: 1px solid #e5e7eb; padding: 0.5em 0.65em; text-align: left; }
.report-email-body th { background: #0f766e; color: white; font-weight: 600; }
.report-email-body tr:nth-child(even) { background: #f9fafb; }
.report-email-body blockquote { border-left: 4px solid #0d9488; margin: 1em 0; padding: 0.5em 1em; background: #f0f4ff; color: #374151; }
.report-email-body img { max-width: 100%; height: auto; display: block; margin: 1rem auto; border-radius: 8px; }
.report-email-body h1, .report-email-body h2, .report-email-body h3 { color: #0f172a; line-height: 1.3; }
.footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
</style>
"""


def _extract_data_uri_images_for_cid(html_fragment: str):
    """
    Sustituye ``src=data:image/...;base64,...`` por ``src=cid:report_inline_N`` y devuelve
    la lista de tuplas ``(cid, bytes_crudos, subtipo)`` para adjuntos inline MIME.
    """
    collected = []
    idx = [0]

    def _repl(match: re.Match) -> str:
        quote = match.group(1)
        subtype = match.group('sub').strip().lower()
        b64 = re.sub(r'\s+', '', match.group('b64'))
        raw = base64.b64decode(b64)
        cid = f'report_inline_{idx[0]}'
        idx[0] += 1
        collected.append((cid, raw, subtype))
        return f'src={quote}cid:{cid}{quote}'

    out = _SRC_DATA_URI_RE.sub(_repl, html_fragment or '')
    return out, collected


def _make_inline_image_part(cid: str, raw: bytes, subtype: str) -> MIMEBase:
    st = (subtype or 'png').lower()
    if st == 'jpg':
        st = 'jpeg'
    if st in ('jpeg', 'png', 'gif'):
        part = MIMEImage(raw, _subtype=st)
    else:
        part = MIMEBase('image', st)
        part.set_payload(raw)
        encoders.encode_base64(part)
    part.add_header('Content-ID', f'<{cid}>')
    ext = 'png' if st not in ('jpeg', 'jpg', 'gif', 'webp') else ('jpg' if st == 'jpeg' else st)
    part.add_header('Content-Disposition', 'inline', filename=f'{cid}.{ext}')
    return part


def _premailer_inline_css(html_document: str) -> str:
    try:
        from premailer import transform

        return transform(html_document)
    except Exception:
        return html_document


def _smtp_send_mime(root: MIMEMultipart, recipients: list[str]) -> None:
    """Envío SMTP usando la misma configuración que Flask-Mail."""
    mstate = current_app.extensions.get('mail')
    if mstate is not None and getattr(mstate, 'suppress', False):
        current_app.logger.info('Correo suprimido (MAIL_SUPPRESS_SEND / testing)')
        return

    cfg = current_app.config
    server = cfg.get('MAIL_SERVER', '127.0.0.1')
    port = int(cfg.get('MAIL_PORT') or 25)
    use_tls = cfg.get('MAIL_USE_TLS', False)
    use_ssl = cfg.get('MAIL_USE_SSL', False)
    username = cfg.get('MAIL_USERNAME')
    password = cfg.get('MAIL_PASSWORD')

    if use_ssl:
        smtp = smtplib.SMTP_SSL(server, port)
    else:
        smtp = smtplib.SMTP(server, port)

    try:
        smtp.set_debuglevel(int(cfg.get('MAIL_DEBUG', 0) or 0))
        if use_tls and not use_ssl:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(root)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


def send_reset_email(user):
    """
    Enviar email con token para resetear contraseña
    """
    token = user.get_reset_token()

    msg = Message(
        'Recuperación de Contraseña - FollowUp',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email]
    )

    reset_url = url_for('auth.reset_password', token=token, _external=True)

    msg.body = f"""Hola {user.username},

Has solicitado recuperar tu contraseña en FollowUp.

Para crear una nueva contraseña, haz click en el siguiente enlace:

{reset_url}

Este enlace es válido por 30 minutos.

Si no solicitaste este cambio, simplemente ignora este email y tu contraseña permanecerá sin cambios.

Saludos,
El equipo de FollowUp
"""

    msg.html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #1e3a8a; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background: #f9fafb; }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background: #10b981;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Recuperación de Contraseña</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{user.username}</strong>,</p>
                <p>Has solicitado recuperar tu contraseña en FollowUp.</p>
                <p>Para crear una nueva contraseña, haz click en el siguiente botón:</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Cambiar mi contraseña</a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    O copia este enlace en tu navegador:<br>
                    <a href="{reset_url}">{reset_url}</a>
                </p>
                <p style="color: #ef4444; font-size: 14px;">
                    ⏰ Este enlace es válido por <strong>30 minutos</strong>.
                </p>
                <p>Si no solicitaste este cambio, simplemente ignora este email y tu contraseña permanecerá sin cambios.</p>
            </div>
            <div class="footer">
                <p>&copy; 2025 FollowUp - Gestión Financiera Personal</p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        mail.send(msg)
        current_app.logger.info(f'Reset email sent to {user.email}')
    except Exception as e:
        current_app.logger.error(f'Failed to send reset email to {user.email}: {str(e)}')
        raise


def send_report_email(user, asset_name, report_title, report_content_markdown, audio_file_path=None):
    """
    Envía el informe por correo:
    - Markdown → HTML (tablas y extensiones ``extra``).
    - Imágenes ``data:image/...;base64`` → adjuntos inline CID (compatibilidad Gmail/Outlook).
    - CSS inlining con premailer para tablas y formato en clientes que ignoran ``<style>``.
    """
    import html as html_module

    md = report_content_markdown or ''
    try:
        import markdown as md_lib

        fragment = md_lib.markdown(
            md,
            extensions=['extra', 'nl2br'],
        )
    except ImportError:
        fragment = md.replace('\n', '<br>')

    fragment_cid, inline_images = _extract_data_uri_images_for_cid(fragment)

    audio_note = ''
    audio_attached = False
    wav_bytes = None
    wav_filename = None
    if audio_file_path:
        from pathlib import Path

        p = Path(audio_file_path)
        if p.exists() and p.is_file():
            wav_filename = f'resumen_audio_{"".join(c if c.isalnum() or c in " -_" else "_" for c in asset_name)[:50].strip() or "informe"}.wav'
            with open(p, 'rb') as f:
                wav_bytes = f.read()
            audio_attached = True
            audio_note = 'Se adjunta el audio resumen (archivo WAV).'

    plain_body = f"""Hola {user.username},

Te enviamos el informe "{report_title}" para {asset_name}.
{audio_note}

Versión HTML con tablas e ilustraciones: abre el mensaje en un cliente que soporte HTML.

Saludos,
El equipo de FollowUp
"""

    inner_report_html = f'<div class="report-email-body">{fragment_cid}</div>'
    safe_title = html_module.escape(report_title or '')
    safe_asset = html_module.escape(asset_name or '')
    safe_username = html_module.escape(user.username or '')
    shell = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{_REPORT_EMAIL_SHELL_CSS}
</head>
<body>
<div class="container">
<div class="header">
<h1>📄 Informe: {safe_title}</h1>
<p>{safe_asset}</p>
</div>
<div class="content">
<p>Hola <strong>{safe_username}</strong>,</p>
<p>Aquí tienes el informe que solicitaste.</p>
{f'<p style="color:#4338ca;font-size:14px;">🎧 Se adjunta el audio resumen (WAV).</p>' if audio_attached else ''}
{inner_report_html}
</div>
<div class="footer">
<p>&copy; 2025 FollowUp - Gestión Financiera Personal</p>
</div>
</div>
</body>
</html>"""

    html_document = _premailer_inline_css(shell)

    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
    if not sender:
        raise ValueError('MAIL_DEFAULT_SENDER / MAIL_USERNAME no configurado')

    subject = f'Informe: {report_title} - {asset_name}'
    root = MIMEMultipart('mixed')
    root['Subject'] = Header(subject, 'utf-8')
    root['From'] = sender if isinstance(sender, str) else formataddr(sender)
    root['To'] = user.email
    root['Date'] = formatdate(localtime=True)

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(plain_body, 'plain', 'utf-8'))

    if inline_images:
        rel = MIMEMultipart('related')
        rel.attach(MIMEText(html_document, 'html', 'utf-8'))
        for cid, raw, subt in inline_images:
            rel.attach(_make_inline_image_part(cid, raw, subt))
        alt.attach(rel)
    else:
        alt.attach(MIMEText(html_document, 'html', 'utf-8'))

    root.attach(alt)

    if wav_bytes and wav_filename:
        wav_part = MIMEAudio(wav_bytes, _subtype='wav')
        wav_part.add_header('Content-Disposition', 'attachment', filename=wav_filename)
        root.attach(wav_part)

    _smtp_send_mime(root, [user.email])
    current_app.logger.info(f'Report email sent to {user.email} (CID inline={len(inline_images)})')
