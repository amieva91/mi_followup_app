"""
Utilidades para envío de emails
"""
from flask import url_for, current_app
from flask_mail import Message
from app import mail


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
    Enviar informe por correo al usuario.
    report_content_markdown: contenido del informe en Markdown (se convierte a HTML internamente)
    audio_file_path: ruta absoluta al archivo WAV del audio resumen (opcional). Si existe, se adjunta.
    """
    try:
        import markdown
        report_content_html = markdown.markdown(report_content_markdown or '', extensions=['extra', 'nl2br'])
    except ImportError:
        report_content_html = (report_content_markdown or '').replace('\n', '<br>')
    msg = Message(
        f'Informe: {report_title} - {asset_name}',
        sender=current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME'),
        recipients=[user.email]
    )
    audio_attached = False
    if audio_file_path:
        from pathlib import Path
        p = Path(audio_file_path)
        if p.exists() and p.is_file():
            with open(p, 'rb') as f:
                safe_name = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in asset_name)[:50]
                msg.attach(
                    filename=f'resumen_audio_{safe_name.strip() or "informe"}.wav',
                    content_type='audio/wav',
                    data=f.read()
                )
            audio_attached = True

    msg.body = f"""Hola {user.username},

Te enviamos el informe "{report_title}" para {asset_name}.
{f'Se adjunta el audio resumen (archivo WAV).' if audio_attached else ''}

Puedes ver el contenido completo en la aplicación FollowUp.

Saludos,
El equipo de FollowUp
"""
    msg.html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #1e3a8a; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background: #f9fafb; }}
            .report {{ background: white; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px; margin-top: 20px; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Informe: {report_title}</h1>
                <p>{asset_name}</p>
            </div>
            <div class="content">
                <p>Hola <strong>{user.username}</strong>,</p>
                <p>Aquí tienes el informe que solicitaste:</p>
                {f'<p class="text-indigo-600 text-sm">🎧 Se adjunta el audio resumen.</p>' if audio_attached else ''}
                <div class="report">
                    {report_content_html}
                </div>
            </div>
            <div class="footer">
                <p>&copy; 2025 FollowUp - Gestión Financiera Personal</p>
            </div>
        </div>
    </body>
    </html>
    """
    mail.send(msg)
    current_app.logger.info(f'Report email sent to {user.email}')

