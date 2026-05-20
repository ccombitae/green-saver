#!/usr/bin/env python3
import psycopg2

# Connection string de Render
DATABASE_URL = "postgresql://greensaver_user:H3qwNmPzKleB7r6HTeGIsYN7AIyGdFYm@dpg-d82jg53bc2fs73b8jl80-a.oregon-postgres.render.com/greensaver"

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
