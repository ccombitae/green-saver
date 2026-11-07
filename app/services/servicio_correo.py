import json
import smtplib
from email.message import EmailMessage
from urllib import error as error_url
from urllib import request as solicitud_url

from app.core.config import settings

ASUNTO = "Cotizacion Green Saver"


def construir_mensaje(destinatario: str, nombre: str, calculo_id: int, materiales: dict, precio_total: float, notas: str) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["Subject"] = ASUNTO
    mensaje["From"] = settings.smtp_from
    mensaje["To"] = destinatario
    mensaje.set_content(
        f"""Hola {nombre},

Te compartimos la cotizacion de tu sistema solar:

- ID de calculo: {calculo_id}
- Tipo de panel: {materiales.get("panelType", "")}
- Tipo de inversor: {materiales.get("inverterType", "")}
- Tipo de bateria: {materiales.get("batteryType", "")}
- Tipo de estructura: {materiales.get("structureType", "")}
- Precio total: {precio_total:,.2f}

Notas:
{notas or "Sin observaciones adicionales."}

Gracias por confiar en Green Saver."""
    )
    return mensaje


def enviar_correo(mensaje: EmailMessage) -> None:
    if settings.sendgrid_api_key:
        if not settings.smtp_from:
            raise ValueError("Falta SENDGRID_FROM_EMAIL o SMTP_FROM para enviar la cotizacion")
        cuerpo = {
            "personalizations": [{"to": [{"email": mensaje["To"]}], "subject": ASUNTO}],
            "from": {"email": settings.smtp_from},
            "content": [{"type": "text/plain", "value": mensaje.get_content()}],
        }
        peticion = solicitud_url.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with solicitud_url.urlopen(peticion, timeout=20):
                return
        except error_url.HTTPError as error:
            detalle = error.read().decode("utf-8", errors="ignore")
            raise ValueError(f"SendGrid HTTP {error.code}: {detalle or error.reason}") from error
        except Exception as error:
            raise ValueError(f"SendGrid no respondió: {error}") from error

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        raise ValueError("SMTP/SendGrid no configurado. Define SMTP_HOST, SMTP_USER y SMTP_PASSWORD o SENDGRID_API_KEY.")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as servidor:
        if settings.smtp_use_tls:
            servidor.starttls()
        servidor.login(settings.smtp_user, settings.smtp_password)
        servidor.send_message(mensaje)
