import mariadb
import os
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="Green Saver API", version="1.0.0")

# ===== CORS CONFIGURATION =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar a dominios específicos en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión a MariaDB
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "greensaver")
DB_USER = os.getenv("DB_USER", "root")
DB_PASWD = os.getenv("DB_PASWD", "")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

conn = None
cursor = None

try:
    conn = mariadb.connect(
        user=DB_USER,
        password=DB_PASWD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)  # devuelve resultados como dict
except mariadb.Error as e:
    print(f"Error conectando a MariaDB: {e}")

# ===== MODELOS PYDANTIC =====
class UsuarioRegistro(BaseModel):
    name: str
    phone: str
    email: str
    password: str
    role: str = "user"

class UsuarioLogin(BaseModel):
    email: str
    password: str

class RecuperarPassword(BaseModel):
    email: str
    newPassword: str

class CalculoCrear(BaseModel):
    email: str
    consumption: float
    estimatedPanels: int
    coverage: float
    estimatedSavings: float
    recommendation: str

# ===== AUTENTICACIÓN =====

@app.post("/auth/register")
async def register(user: UsuarioRegistro):
    """Registrar nuevo usuario con validaciones"""
    try:
        # Verificar si el usuario ya existe
        cursor.execute("SELECT email FROM usuarios WHERE email = ?", (user.email,))
        if cursor.fetchone():
            return {"detail": "El usuario ya existe", "status": 400}
        
        # Insertar nuevo usuario (en producción: hashear password con bcrypt)
        cursor.execute(
            """INSERT INTO usuarios (nombre, email, telefono, password, rol, created_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user.name, user.email, user.phone, user.password, user.role, datetime.now())
        )
        conn.commit()
        
        usuario_id = cursor.lastrowid
        
        return {
            "id": usuario_id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "role": user.role,
            "token": None
        }
    except Exception as e:
        return {"detail": str(e), "status": 500}

@app.post("/auth/login")
async def login(credentials: UsuarioLogin):
    """Autenticar usuario y retornar sesión"""
    try:
        cursor.execute(
            "SELECT id, nombre, email, telefono, rol FROM usuarios WHERE email = ? AND password = ?",
            (credentials.email, credentials.password)
        )
        user = cursor.fetchone()
        
        if not user:
            return {"detail": "Credenciales incorrectas", "status": 401}
        
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["nombre"],
            "phone": user["telefono"],
            "role": user["rol"],
            "token": None
        }
    except Exception as e:
        return {"detail": str(e), "status": 500}

@app.post("/auth/recover-password")
async def recover_password(payload: RecuperarPassword):
    """Actualizar contraseña en MariaDB usando email"""
    try:
        if cursor is None or conn is None:
            raise HTTPException(status_code=503, detail="Base de datos no disponible")

        email = payload.email.strip().lower()
        new_password = payload.newPassword.strip()

        if not email or not new_password:
            raise HTTPException(status_code=400, detail="Correo y nueva contraseña son obligatorios")

        if email == "admin@greensaver.com":
            raise HTTPException(status_code=400, detail="La contraseña del administrador fijo no se puede recuperar desde esta pantalla")

        cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if not existing_user:
            raise HTTPException(status_code=404, detail="No existe una cuenta registrada con ese correo")

        cursor.execute(
            "UPDATE usuarios SET password = ?, updated_at = ? WHERE email = ?",
            (new_password, datetime.now(), email)
        )
        conn.commit()

        return {
            "message": "Contraseña actualizada",
            "email": email,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/me")
async def current_user(email: str):
    """Obtener datos del usuario actual"""
    try:
        cursor.execute(
            "SELECT id, nombre, email, telefono, rol FROM usuarios WHERE email = ?",
            (email,)
        )
        user = cursor.fetchone()
        
        if not user:
            return {"detail": "Usuario no encontrado", "status": 404}
        
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["nombre"],
            "phone": user["telefono"],
            "role": user["rol"]
        }
    except Exception as e:
        return {"detail": str(e), "status": 500}

# ------------------- CRUD USUARIOS -------------------
@app.get("/usuarios")
async def get_usuarios():
    cursor.execute("SELECT * FROM usuarios")
    return cursor.fetchall()

@app.post("/usuarios")
async def insert_usuario(nombre: str, ciudad: str, consumo_mensual: float):
    cursor.execute("INSERT INTO usuarios (nombre, ciudad, consumo_mensual) VALUES (?, ?, ?)",
                   (nombre, ciudad, consumo_mensual))
    conn.commit()
    return {"message": "Usuario insertado"}

@app.put("/usuarios/{id}")
async def update_usuario(id: int, nombre: str, ciudad: str, consumo_mensual: float):
    cursor.execute("UPDATE usuarios SET nombre=?, ciudad=?, consumo_mensual=? WHERE id=?",
                   (nombre, ciudad, consumo_mensual, id))
    conn.commit()
    return {"message": "Usuario actualizado"}

@app.delete("/usuarios/{id}")
async def delete_usuario(id: int):
    cursor.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit()
    return {"message": "Usuario eliminado"}

# ------------------- CRUD PROVEEDORES -------------------
@app.get("/proveedores")
async def get_proveedores():
    cursor.execute("SELECT * FROM proveedores")
    return cursor.fetchall()

@app.post("/proveedores")
async def insert_proveedor(nombre_empresa: str, contacto: str, telefono: str, direccion: str, tipo_equipo: str):
    cursor.execute("INSERT INTO proveedores (nombre_empresa, contacto, telefono, direccion, tipo_equipo) VALUES (?, ?, ?, ?, ?)",
                   (nombre_empresa, contacto, telefono, direccion, tipo_equipo))
    conn.commit()
    return {"message": "Proveedor insertado"}

@app.put("/proveedores/{id}")
async def update_proveedor(id: int, nombre_empresa: str, contacto: str, telefono: str, direccion: str, tipo_equipo: str):
    cursor.execute("UPDATE proveedores SET nombre_empresa=?, contacto=?, telefono=?, direccion=?, tipo_equipo=? WHERE id=?",
                   (nombre_empresa, contacto, telefono, direccion, tipo_equipo, id))
    conn.commit()
    return {"message": "Proveedor actualizado"}

@app.delete("/proveedores/{id}")
async def delete_proveedor(id: int):
    cursor.execute("DELETE FROM proveedores WHERE id=?", (id,))
    conn.commit()
    return {"message": "Proveedor eliminado"}

# ------------------- CRUD PANELES -------------------
@app.get("/paneles")
async def get_paneles():
    cursor.execute("SELECT * FROM paneles")
    return cursor.fetchall()

@app.post("/paneles")
async def insert_panel(modelo: str, potencia_w: float, precio: float, proveedor_id: int):
    cursor.execute("INSERT INTO paneles (modelo, potencia_w, precio, proveedor_id) VALUES (?, ?, ?, ?)",
                   (modelo, potencia_w, precio, proveedor_id))
    conn.commit()
    return {"message": "Panel insertado"}

@app.put("/paneles/{id}")
async def update_panel(id: int, modelo: str, potencia_w: float, precio: float, proveedor_id: int):
    cursor.execute("UPDATE paneles SET modelo=?, potencia_w=?, precio=?, proveedor_id=? WHERE id=?",
                   (modelo, potencia_w, precio, proveedor_id, id))
    conn.commit()
    return {"message": "Panel actualizado"}

@app.delete("/paneles/{id}")
async def delete_panel(id: int):
    cursor.execute("DELETE FROM paneles WHERE id=?", (id,))
    conn.commit()
    return {"message": "Panel eliminado"}

# ------------------- CRUD INVERSORES -------------------
@app.get("/inversores")
async def get_inversores():
    cursor.execute("SELECT * FROM inversores")
    return cursor.fetchall()

@app.post("/inversores")
async def insert_inversor(potencia_kw: float, voltaje: str, precio: float, proveedor_id: int):
    cursor.execute("INSERT INTO inversores (potencia_kw, voltaje, precio, proveedor_id) VALUES (?, ?, ?, ?)",
                   (potencia_kw, voltaje, precio, proveedor_id))
    conn.commit()
    return {"message": "Inversor insertado"}

@app.put("/inversores/{id}")
async def update_inversor(id: int, potencia_kw: float, voltaje: str, precio: float, proveedor_id: int):
    cursor.execute("UPDATE inversores SET potencia_kw=?, voltaje=?, precio=?, proveedor_id=? WHERE id=?",
                   (potencia_kw, voltaje, precio, proveedor_id, id))
    conn.commit()
    return {"message": "Inversor actualizado"}

@app.delete("/inversores/{id}")
async def delete_inversor(id: int):
    cursor.execute("DELETE FROM inversores WHERE id=?", (id,))
    conn.commit()
    return {"message": "Inversor eliminado"}

# ------------------- CRUD BATERIAS -------------------
@app.get("/baterias")
async def get_baterias():
    cursor.execute("SELECT * FROM baterias")
    return cursor.fetchall()

@app.post("/baterias")
async def insert_bateria(capacidad_kwh: float, tipo: str, precio: float, proveedor_id: int):
    cursor.execute("INSERT INTO baterias (capacidad_kwh, tipo, precio, proveedor_id) VALUES (?, ?, ?, ?)",
                   (capacidad_kwh, tipo, precio, proveedor_id))
    conn.commit()
    return {"message": "Batería insertada"}

@app.put("/baterias/{id}")
async def update_bateria(id: int, capacidad_kwh: float, tipo: str, precio: float, proveedor_id: int):
    cursor.execute("UPDATE baterias SET capacidad_kwh=?, tipo=?, precio=?, proveedor_id=? WHERE id=?",
                   (capacidad_kwh, tipo, precio, proveedor_id, id))
    conn.commit()
    return {"message": "Batería actualizada"}

@app.delete("/baterias/{id}")
async def delete_bateria(id: int):
    cursor.execute("DELETE FROM baterias WHERE id=?", (id,))
    conn.commit()
    return {"message": "Batería eliminada"}

# ------------------- CRUD CALCULOS SISTEMA -------------------
@app.get("/calculos")
async def get_calculos():
    cursor.execute("SELECT * FROM calculos_sistema")
    return cursor.fetchall()

@app.post("/calculos")
async def insert_calculo_v2(calculo: CalculoCrear):
    """Crear nuevo cálculo (versión JSON con email)"""
    try:
        cursor.execute("""
            INSERT INTO calculos_sistema (email, consumption, estimatedPanels, coverage, 
                                         estimatedSavings, recommendation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            calculo.email,
            calculo.consumption,
            calculo.estimatedPanels,
            calculo.coverage,
            calculo.estimatedSavings,
            calculo.recommendation,
            datetime.now()
        ))
        conn.commit()
        
        return {
            "id": cursor.lastrowid,
            "email": calculo.email,
            "consumption": calculo.consumption,
            "estimatedPanels": calculo.estimatedPanels,
            "coverage": calculo.coverage,
            "estimatedSavings": calculo.estimatedSavings,
            "recommendation": calculo.recommendation,
            "created_at": datetime.now().isoformat()
        }
    except Exception as e:
        return {"detail": str(e), "status": 500}

@app.put("/calculos/{id}")
async def update_calculo(id: int, usuario_id: int, panel_id: int, inversor_id: int, bateria_id: int,
                         paneles_necesarios: int, inversor_kw: float, bateria_kwh: float, costo_total: float):
    cursor.execute("""UPDATE calculos_sistema SET usuario_id=?, panel_id=?, inversor_id=?, bateria_id=?, 
        paneles_necesarios=?, inversor_kw=?, bateria_kwh=?, costo_total=? WHERE id=?""",
        (usuario_id, panel_id, inversor_id, bateria_id, paneles_necesarios, inversor_kw, bateria_kwh, costo_total, id))
    conn.commit()
    return {"message": "Cálculo actualizado"}

@app.delete("/calculos/{id}")
async def delete_calculo(id: int):
    cursor.execute("DELETE FROM calculos_sistema WHERE id=?", (id,))
    conn.commit()
    return {"message": "Cálculo eliminado"}

# ------------------- REPORTE GENERAL -------------------
@app.get("/greensaver/report")
async def reporte_general():
    sql = """
    SELECT 
        u.nombre,
        p.modelo AS panel,
        i.potencia_kw AS inversor,
        b.capacidad_kwh AS bateria,
        c.paneles_necesarios,
        c.costo_total
    FROM calculos_sistema c
    JOIN usuarios u ON c.usuario_id = u.id
    JOIN paneles p ON c.panel_id = p.id
    JOIN inversores i ON c.inversor_id = i.id
    JOIN baterias b ON c.bateria_id = b.id
    """
    cursor.execute(sql)
    return cursor.fetchall()

@app.get("/")
async def root():
    return {"message": "Bienvenido a Green Saber API 🚀"}