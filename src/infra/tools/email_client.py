"""
Cliente SMTP asíncrono para envío de emails transaccionales.
Usa aiosmtplib para no bloquear el event loop.
"""

from __future__ import annotations

import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from infra.config.database import settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Error al enviar email."""
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


async def send_email(to: str, subject: str, html_body: str) -> None:
    """
    Envía un email vía SMTP.
    Si las credenciales SMTP no están configuradas, loguea el email
    en vez de enviarlo (útil para desarrollo).
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "SMTP no configurado. Email que se habría enviado:\n"
            f"  To: {to}\n"
            f"  Subject: {subject}\n"
            f"  Body: {html_body[:200]}..."
        )
        return

    message = MIMEMultipart("alternative")
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )
        logger.info(f"Email enviado a {to}: {subject}")
    except Exception as e:
        logger.error(f"Error enviando email a {to}: {e}")
        raise EmailSendError(f"No se pudo enviar el email: {e}")


async def send_verification_email(to: str, full_name: str, verification_token: str) -> None:
    """
    Envía el email de verificación con un link al frontend.
    El frontend recibirá el token y llamará al endpoint /auth/verify-email.
    """
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            h1 {{ color: #1a1a1a; font-size: 22px; margin-bottom: 8px; }}
            p {{ color: #555; font-size: 15px; line-height: 1.6; }}
            .btn {{ display: inline-block; background: #6C63FF; color: #ffffff; text-decoration: none; padding: 12px 32px; border-radius: 8px; font-weight: 600; font-size: 15px; margin: 20px 0; }}
            .footer {{ font-size: 12px; color: #999; margin-top: 30px; border-top: 1px solid #eee; padding-top: 16px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Verifica tu cuenta, {full_name}</h1>
            <p>Gracias por registrarte en <strong>{settings.APP_NAME}</strong>. Para completar la verificación de tu cuenta, haz clic en el siguiente botón:</p>
            <a href="{verification_url}" class="btn">Verificar mi email</a>
            <p>Si no creaste esta cuenta, puedes ignorar este email.</p>
            <div class="footer">
                <p>Este enlace expira en {settings.JWT_VERIFICATION_TOKEN_EXPIRE_HOURS} horas.</p>
                <p>Si el botón no funciona, copia y pega esta URL en tu navegador:<br>
                <span style="word-break: break-all; color: #6C63FF;">{verification_url}</span></p>
            </div>
        </div>
    </body>
    </html>
    """

    await send_email(
        to=to,
        subject=f"Verifica tu cuenta en {settings.APP_NAME}",
        html_body=html,
    )
