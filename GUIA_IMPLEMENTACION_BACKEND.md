# Guía de Implementación: Backend FastAPI + MariaDB

**Fecha**: 9 de abril de 2026  
**Repositorio Backend**: https://github.com/sdurangoc/greensaver.git  
**Cambios**: Integración de autenticación y endpoints JSON para frontend Expo

---

## 1. Requisitos Previos

Asegúrate de tener instalado:
```bash
pip install fastapi uvicorn python-mariadb pydantic
```

O actualiza con:
```bash
pip install --upgrade fastapi uvicorn python-mariadb pydantic
```

---

## 2. Cambios en el Código Backend

### A. Archivo `backend/main.py` ✅ (Ya integrado)

**Lo que cambió:**
1. ✅ Agregados imports de CORS y Pydantic
2. ✅ Configurado middleware CORS (acceso desde Expo web/mobile)
3. ✅ Agregados 3 modelos Pydantic: UsuarioRegistro, UsuarioLogin, CalculoCrear
4. ✅ Agregados 3 endpoints de autenticación:
   - POST /auth/register
   - POST /auth/login
   - GET /auth/me
5. ✅ Actualizado POST /calculos para aceptar JSON en lugar de query params

**Los CRUD existentes se mantienen intactos** (usuarios, proveedores, paneles, inversores, baterías, reporte)

---

## 3. Crear Tablas en MariaDB

### Opción A: Ejecutar script SQL (Recomendado)

```bash
mysql -u root -p greensaver < backend/crear_tablas.sql
```

O si tienes MariaDB:
```bash
mariadb -u root -p greensaver < backend/crear_tablas.sql
```

### Opción B: Ejecutar manualmente con cliente MySQL

1. Abre MySQL Workbench o cliente MariaDB
2. Conecta a tu base de datos `greensaver` con usuario `root`
3. Copia y pega el contenido de `backend/crear_tablas.sql`
4. Ejecuta (Ctrl+Enter)

### Opción C: Python directamente en terminal

```python
import mariadb

conn = mariadb.connect(
    user="root",
    password="",
    host="localhost",
    port=3306,
    database="greensaver"
)
cursor = conn.cursor()

# Leer el archivo SQL
with open("backend/crear_tablas.sql", "r", encoding="utf-8") as f:
    # Dividir por ; y ejecutar cada sentencia
    sql_statements = f.read().split(";")
    for statement in sql_statements:
        statement = statement.strip()
        if statement:
            cursor.execute(statement)
            conn.commit()

conn.close()
print("✅ Tablas creadas exitosamente")
```

---

## 4. Ejecutar Backend

### Desarrollo (con auto-reload)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Producción

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete
```

---

## 5. Confirmar Integración

### A. Abrir en navegador

Navega a http://localhost:8000 y deberías ver:
```json
{
  "message": "Bienvenido a Green Saver API 🚀",
  "version": "1.0.0"
}
```

### B. Probar endpoints con curl

**Registro:**
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Juan Pérez",
    "phone": "+34 912 345 678",
    "email": "juan@example.com",
    "password": "Password123",
    "role": "user"
  }'
```

**Login:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan@example.com",
    "password": "Password123"
  }'
```

**Crear Cálculo:**
```bash
curl -X POST "http://localhost:8000/calculos" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan@example.com",
    "consumption": 1500,
    "estimatedPanels": 20,
    "coverage": 100,
    "estimatedSavings": 975,
    "recommendation": "Sistema altamente viable"
  }'
```

**Obtener Cálculos:**
```bash
curl -X GET "http://localhost:8000/calculos"
```

---

## 6. Archivos Modificados

```
✅ backend/main.py              (Integración completa)
✅ backend/crear_tablas.sql    (DDL para tablas + índices + usuario admin)
```

---

## 7. Conexión con Frontend

Tu app React Native en `c:\Users\combi\green-saver` ya está configurada para conectar a este backend.

**Variable de entorno:**
```bash
set EXPO_PUBLIC_API_URL=http://localhost:8000
npm start
```

O crea `.env.local` en la raíz del frontend:
```
EXPO_PUBLIC_API_URL=http://localhost:8000
```

**La app automáticamente:**
- Intenta conectar a backend
- Si falla → fallback a AsyncStorage local
- Funciona 100% sin backend si es necesario

---

## 8. Mapeo de Endpoints

| Función | Método | Endpoint | Estado |
|---------|--------|----------|--------|
| Register | POST | /auth/register | ✅ Nuevo |
| Login | POST | /auth/login | ✅ Nuevo |
| Get Me | GET | /auth/me | ✅ Nuevo |
| Get Cálculos | GET | /calculos | ✅ Existente |
| Create Cálculo | POST | /calculos | ✅ Actualizado (JSON) |
| Get Usuarios | GET | /usuarios | ✅ Existente |
| ... | ... | ... | ✅ Otros CRUD existentes |

---

## 9. Estructura de Respuestas

### POST /auth/register - 201

```json
{
  "id": 1,
  "email": "juan@example.com",
  "name": "Juan Pérez",
  "phone": "+34 912 345 678",
  "role": "user",
  "token": null
}
```

### POST /auth/login - 200

```json
{
  "id": 1,
  "email": "juan@example.com",
  "name": "Juan Pérez",
  "phone": "+34 912 345 678",
  "role": "user",
  "token": null
}
```

### POST /calculos - 201

```json
{
  "id": 101,
  "email": "juan@example.com",
  "consumption": 1500,
  "estimatedPanels": 20,
  "coverage": 100,
  "estimatedSavings": 975,
  "recommendation": "Sistema altamente viable",
  "created_at": "2026-04-09T15:45:22.123456"
}
```

---

## 10. Solución de Problemas

### Error: "Can't connect to MariaDB"
```
Solución: Asegúrate de que:
1. MariaDB está corriendo (services en Windows)
2. Usuario "root" existe con contraseña vacía
3. Base de datos "greensaver" existe
```

### Error: "CORS error" en frontend
```
Solución: Ya está configurado con allow_origins=["*"]
Si aún falla, verifica que uvicorn está corriendo en puerto 8000
```

### Error: "Module not found: pydantic"
```
Solución:
pip install pydantic==2.0.0 fastapi uvicorn python-mariadb
```

---

## 11. Pasos Finales

1. ✅ Actualizar `backend/main.py`
2. ✅ Crear `backend/crear_tablas.sql` (Ya creado)
3. ⏳ Ejecutar script SQL en MariaDB
4. ⏳ Lanzar backend: `uvicorn main:app --reload --port 8000`
5. ⏳ Probar endpoints con curl o Postman
6. ⏳ Conectar frontend (ya está listo)

---

## 12. Comando Rápido (One-liner)

```bash
cd C:\Users\combi\greensaver-backend\backend && uvicorn main:app --reload --port 8000
```

---

**¿Listo?** 🚀 La integración está COMPLETA del lado backend.
Ahora solo necesitas ejecutar las tablas SQL y lanzar el servidor.
