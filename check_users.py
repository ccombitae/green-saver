#!/usr/bin/env python3
import os
import sys

import psycopg2

# La cadena de conexión se lee de la variable de entorno DATABASE_URL.
# Nunca escribir credenciales en el código.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("Define la variable de entorno DATABASE_URL antes de ejecutar este script.")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("USUARIOS REGISTRADOS EN RENDER")
    print("=" * 60)
    
    # Consultar todos los usuarios
    cursor.execute("SELECT id, nombre, email, telefono, rol, created_at FROM usuarios ORDER BY created_at DESC;")
    
    usuarios = cursor.fetchall()
    
    if not usuarios:
        print("❌ No hay usuarios registrados aún.")
    else:
        print(f"\n✅ Total de usuarios: {len(usuarios)}\n")
        for row in usuarios:
            id_user, nombre, email, telefono, rol, created_at = row
            print(f"ID: {id_user}")
            print(f"  Nombre: {nombre}")
            print(f"  Email: {email}")
            print(f"  Teléfono: {telefono}")
            print(f"  Rol: {rol}")
            print(f"  Registrado: {created_at}")
            print("-" * 60)
    
    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
