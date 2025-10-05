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

