#!/usr/bin/env python3
import psycopg2
import sys

# Connection string
DATABASE_URL = "postgresql://greensaver_user:H3qwNmPzKleB7r6HTeGIsYN7AIyGdFYm@dpg-d82jg53bc2fs73b8jl80-a.oregon-postgres.render.com/greensaver"

try:
    # Connect
    print("Conectando a Render Postgres...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("✓ Conexión establecida")

    # Read schema
    print("Leyendo schema.sql...")
    with open('app/db/schema.sql', 'r') as f:
        schema = f.read()

    # Execute schema
    print("Ejecutando SQL...")
    cursor.execute(schema)
    conn.commit()
    print("✓ Schema ejecutado exitosamente")

    # Verify tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public'
    """)
    tables = cursor.fetchall()
    print("\nTablas creadas:")
    for table in tables:
        print(f"  - {table[0]}")

    cursor.close()
    conn.close()
    print("\n✓ Base de datos configurada correctamente")

except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
