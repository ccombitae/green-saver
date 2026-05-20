import json
import smtplib
from urllib import error as urllib_error
from urllib import request as urllib_request
from email.message import EmailMessage

from app.core.config import settings
from app.db.database import db_cursor
from app.schemas.quotes import QuoteSendRequest
from app.services.system_service import save_system_for_email


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
                accepted_at TIMESTAMP,
                installation_date VARCHAR(50),
                FOREIGN KEY (calculation_id) REFERENCES calculos_sistema(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute("ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP")
        cursor.execute("ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS installation_date VARCHAR(50)")


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
                sent_at,
                accepted_at,
                installation_date
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
    if settings.sendgrid_api_key:
        if not settings.smtp_from:
            raise ValueError("Falta SENDGRID_FROM_EMAIL o SMTP_FROM para enviar la cotizacion")

        email_payload = {
            "personalizations": [
                {
                    "to": [{"email": payload.clientEmail}],
                    "subject": "Cotizacion Green Saver",
                }
            ],
            "from": {"email": settings.smtp_from},
            "content": [
                {
                    "type": "text/plain",
                    "value": _build_quote_email(payload).get_content(),
                }
            ],
        }

        request = urllib_request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(email_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=20):
                return
        except urllib_error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"SendGrid HTTP {exc.code}: {error_body or exc.reason}") from exc
        except Exception as exc:
            raise ValueError(f"SendGrid no respondió: {exc}") from exc

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        raise ValueError("SMTP/SendGrid no configurado. Define SMTP_HOST, SMTP_USER y SMTP_PASSWORD o SENDGRID_API_KEY.")

    message = _build_quote_email(payload)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def _update_quote_status(quote_id: int, status: str) -> None:
    try:
        with db_cursor() as cursor:
            cursor.execute(
                """
                UPDATE cotizaciones
                SET status = %s
                WHERE id = %s
                """,
                (status, quote_id),
            )
    except Exception:
        pass


def _estimate_capacity_kwp(calculation: dict) -> float:
    consumption = calculation.get("consumption")

    try:
      if consumption is not None:
        return round((float(consumption) / 30) / 4, 2)
    except (TypeError, ValueError):
      pass

    estimated_panels = calculation.get("estimatedpanels")
    try:
      if estimated_panels is not None:
        return round(float(estimated_panels) * 0.55, 2)
    except (TypeError, ValueError):
      pass

    return 0.5


def accept_quote(quote_id: int, install_date: str) -> dict:
    _ensure_quotes_table()

    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                q.id,
                q.calculation_id,
                q.client_email,
                q.client_name,
                q.total_price,
                q.notes,
                q.materials,
                q.status,
                q.sent_at,
                c.email,
                c.consumption,
                c.estimatedpanels,
                c.coverage,
                c.estimatedsavings,
                c.recommendation
            FROM cotizaciones q
            INNER JOIN calculos_sistema c ON c.id = q.calculation_id
            WHERE q.id = %s
            """,
            (quote_id,),
        )
        quote = cursor.fetchone()

        if not quote:
            raise ValueError("La cotización no existe")

    materials = quote.get("materials") or {}
    installed_system = {
        "capacity": f'{_estimate_capacity_kwp(quote)} kWp',
        "panels": f'{quote.get("estimatedpanels") or 0} paneles',
        "inverter": materials.get("inverterType", ""),
        "battery": materials.get("batteryType", ""),
        "installDate": install_date,
        "panelType": materials.get("panelType", ""),
        "structureType": materials.get("structureType", ""),
        "sourceQuoteId": quote_id,
        "sourceClientEmail": quote.get("client_email", ""),
    }

    saved_system = save_system_for_email(quote["client_email"], installed_system)

    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE cotizaciones
            SET status = 'accepted',
                accepted_at = NOW(),
                installation_date = %s
            WHERE id = %s
            """,
            (install_date, quote_id),
        )

    return {
        "quoteId": quote_id,
        "status": "accepted",
        "installDate": install_date,
        "system": saved_system,
    }


def send_quote(payload: QuoteSendRequest) -> dict:
    _ensure_quotes_table()

    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM calculos_sistema WHERE id = %s", (payload.calculationId,))
        calculation = cursor.fetchone()
        if not calculation:
            raise ValueError("El calculo seleccionado no existe")

    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO cotizaciones (
                calculation_id, client_email, client_name, total_price,
                notes, materials, status, sent_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, 'pending', NOW())
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

    quote_status = "sent"
    email_error = None

    try:
        _send_email(payload)
    except Exception as exc:
        quote_status = "failed"
        email_error = str(exc)
    finally:
        _update_quote_status(created["id"], quote_status)

    response = {
        "id": created["id"],
        "calculationId": payload.calculationId,
        "clientEmail": payload.clientEmail,
        "status": quote_status,
        "sentAt": created["sent_at"].isoformat(),
    }

    if email_error:
        response["emailError"] = email_error

    return response
