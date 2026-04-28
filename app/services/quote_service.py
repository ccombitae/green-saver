import json
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.db.database import db_cursor
from app.schemas.quotes import QuoteSendRequest


QUOTE_OPTIONS = {
    "panelTypes": [
        "Monocristalino 550W",
        "Monocristalino 600W",
        "Bifacial 550W",
    ],
    "inverterTypes": [
        "Inversor Hibrido 5kW",
        "Inversor Hibrido 8kW",
        "Microinversor 2kW",
    ],
    "batteryTypes": [
        "Bateria LiFePO4 5kWh",
        "Bateria LiFePO4 10kWh",
        "Sin bateria",
    ],
    "structureTypes": [
        "Estructura coplanar aluminio",
        "Estructura inclinada aluminio",
        "Estructura suelo galvanizada",
    ],
}


def _ensure_quotes_table():
    with db_cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cotizaciones (
                id SERIAL PRIMARY KEY,
                calculation_id INT NOT NULL,
                client_email VARCHAR(255) NOT NULL,
                client_name VARCHAR(255) NOT NULL,
                total_price NUMERIC(12, 2) NOT NULL,
                notes TEXT,
                materials JSONB NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'sent',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (calculation_id) REFERENCES calculos_sistema(id) ON DELETE CASCADE
            )
            """
        )


def list_quote_options() -> dict:
    return QUOTE_OPTIONS


def list_quote_calculations() -> list[dict]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                c.id,
                c.email,
                COALESCE(u.nombre, c.email) AS client_name,
                c.consumption,
                c.estimatedpanels,
                c.coverage,
                c.estimatedsavings,
                c.recommendation,
                c.created_at
            FROM calculos_sistema c
            LEFT JOIN usuarios u ON LOWER(u.email) = LOWER(c.email)
            ORDER BY c.created_at DESC
            """
        )
        return cursor.fetchall()


def list_sent_quotes() -> list[dict]:
    _ensure_quotes_table()
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                calculation_id,
                client_email,
                client_name,
                total_price,
                notes,
                materials,
                status,
                sent_at
            FROM cotizaciones
            ORDER BY sent_at DESC
            """
        )
        return cursor.fetchall()


def _build_quote_email(payload: QuoteSendRequest) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Cotizacion Green Saver"
    message["From"] = settings.smtp_from
    message["To"] = payload.clientEmail

    body = f"""
Hola {payload.clientName},

Te compartimos la cotizacion de tu sistema solar:

- ID de calculo: {payload.calculationId}
- Tipo de panel: {payload.materials.panelType}
- Tipo de inversor: {payload.materials.inverterType}
- Tipo de bateria: {payload.materials.batteryType}
- Tipo de estructura: {payload.materials.structureType}
- Precio total: USD {payload.totalPrice:.2f}

Notas:
{payload.notes or 'Sin observaciones adicionales.'}

Gracias por confiar en Green Saver.
""".strip()

    message.set_content(body)
    return message


def _send_email(payload: QuoteSendRequest):
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        raise ValueError("SMTP no configurado. Define SMTP_HOST, SMTP_USER y SMTP_PASSWORD en Azure.")

    message = _build_quote_email(payload)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def send_quote(payload: QuoteSendRequest) -> dict:
    _ensure_quotes_table()

    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM calculos_sistema WHERE id = %s", (payload.calculationId,))
        calculation = cursor.fetchone()
        if not calculation:
            raise ValueError("El calculo seleccionado no existe")

    _send_email(payload)

    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO cotizaciones (
                calculation_id, client_email, client_name, total_price,
                notes, materials, status, sent_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, 'sent', NOW())
            RETURNING id, sent_at
            """,
            (
                payload.calculationId,
                payload.clientEmail,
                payload.clientName,
                payload.totalPrice,
                payload.notes,
                json.dumps(payload.materials.model_dump()),
            ),
        )
        created = cursor.fetchone()

    return {
        "id": created["id"],
        "calculationId": payload.calculationId,
        "clientEmail": payload.clientEmail,
        "status": "sent",
        "sentAt": created["sent_at"].isoformat(),
    }
