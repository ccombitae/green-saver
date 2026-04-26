# Green Saver Backend

Backend FastAPI organizado para despliegue en Azure App Service con base de datos PostgreSQL.

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

Configura estas variables en Azure App Service o en tu entorno local:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/greensaver
APP_NAME=Green Saver API
APP_VERSION=1.0.0
CORS_ORIGINS=*
```

## Ejecutar localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Comando de inicio para Azure

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 app.main:app
```

## Endpoints principales

- `GET /`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/recover-password`
- `GET /auth/me`
- `GET /calculos`
- `POST /calculos`
- `GET /usuarios`

## Nota

La carpeta `backend/` original se conserva solo como referencia historica. El punto de entrada nuevo es `app/main.py`.

## Base de datos

Ejecuta `app/db/schema.sql` en tu servidor PostgreSQL de Azure para crear las tablas iniciales.
