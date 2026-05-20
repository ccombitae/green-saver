# Green Saver Backend

Backend FastAPI organizado para despliegue en Render con base de datos PostgreSQL.

## Estructura

```text
green-saver/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── database.py
│   ├── models/
│   ├── schemas/
│   ├── routes/
│   │   ├── auth.py
│   │   ├── solar.py
│   │   └── users.py
│   └── services/
├── requirements.txt
├── README.md
├── .gitignore
└── alembic/
```

## Variables de entorno

Configura estas variables en Render o en tu entorno local:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/greensaver
APP_NAME=Green Saver API
APP_VERSION=1.0.0
CORS_ORIGINS=*
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=tu_sendgrid_api_key
SMTP_FROM=tu_correo_verificado@tudominio.com
SENDGRID_API_KEY=tu_sendgrid_api_key
SENDGRID_FROM_EMAIL=tu_correo_verificado@tudominio.com
```

Si usas SendGrid vía SMTP, en Render deja estos valores:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<tu_api_key_de_sendgrid>
SMTP_FROM=<correo_verificado_en_sendgrid>
```

Si prefieres usar las variables directas de SendGrid, también puedes definir:

```env
SENDGRID_API_KEY=<tu_api_key_de_sendgrid>
SENDGRID_FROM_EMAIL=<correo_verificado_en_sendgrid>
```

## Flujo de cotizaciones y sistemas

- `POST /quotes/send` crea la cotización y, si el correo falla, igual la guarda con estado `failed`.
- `POST /quotes/{quote_id}/accept` marca la cotización como `accepted`, pide solo la fecha de instalación y guarda el sistema instalado del cliente.
- `GET /systems?email=correo@cliente.com` devuelve el sistema instalado del cliente.
- `POST /systems/assign` permite al administrador asignar un sistema manualmente.

## Ejecutar localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Comando de inicio para Render

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 app.main:app
```

## Endpoints principales

- `GET /`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/recover-password`
- `GET /auth/me`
- `GET /calculos`
- `POST /calculos`
- `GET /usuarios`
- `GET /quotes`
- `POST /quotes/send`
- `POST /quotes/{quote_id}/accept`
- `GET /systems`
- `POST /systems/assign`

## Autenticación y permisos

- `POST /auth/login` y `POST /auth/register` emiten `access_token` y `refresh_token`.
- Las rutas `/calculos`, `/usuarios`, `/quotes` y `/auth/me` requieren `Authorization: Bearer <token>`.
- `/usuarios`, `/quotes` y `GET /calculos/reporte` quedan protegidas para rol `admin`.
- `POST /auth/refresh` renueva la sesión usando el `refresh_token`.

## Nota

La carpeta `backend/` original se conserva solo como referencia historica. El punto de entrada nuevo es `app/main.py`.

## Base de datos

Ejecuta `app/db/schema.sql` en tu servidor PostgreSQL de Render para crear las tablas iniciales.

## Prueba exacta de extremo a extremo

1. Publica el backend en Render y verifica que la URL pública responda en `/docs`.
2. Crea o reutiliza un usuario cliente y genera un cálculo.
3. Desde el panel admin, abre `Enviar cotización`, selecciona el cálculo y envíalo.
4. En la lista de cotizaciones enviadas, pulsa `Aceptar cotización`.
5. Ingresa la fecha de instalación y confirma.
6. Inicia sesión como ese cliente y revisa `Mi sistema instalado`.
7. Confirma que el sistema aparece con la fecha de instalación y que las tareas de mantenimiento siguen visibles.
