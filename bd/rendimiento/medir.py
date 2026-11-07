import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg2

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[1]
REPETICIONES = 7

CASOS = [
    {
        "nombre": "Historial de un usuario (GET /calculos)",
        "antes": """SELECT c.id, c.consumo_mensual_kwh, c.paneles, c.cobertura_pct, c.ahorro_estimado_cop, c.creado_en
                    FROM calculos c JOIN usuarios u ON u.id = c.usuario_id
                    WHERE u.correo = 'usuario4321@prueba.com'
                    ORDER BY c.creado_en DESC""",
        "despues": None,
        "cambio": "Índice compuesto ix_calculos_usuario_fecha (usuario_id, creado_en DESC): filtra y entrega el orden",
        "tabla": "calculos",
    },
    {
        "nombre": "Inicio de sesión: búsqueda por correo",
        "antes": "SELECT id, contrasena_hash FROM usuarios WHERE lower(correo) = lower('Usuario4321@Prueba.com')",
        "despues": "SELECT id, contrasena_hash FROM usuarios WHERE correo = 'usuario4321@prueba.com'",
        "cambio": "Consulta sargable: el correo se guarda normalizado (CHECK) y se compara sin funciones sobre la columna",
        "tabla": "usuarios",
    },
    {
        "nombre": "Resumen de ahorro de un usuario",
        "antes": """SELECT count(*), sum(ahorro_estimado_cop), round(avg(paneles), 2)
                    FROM calculos WHERE usuario_id = 4321""",
        "despues": None,
        "cambio": "El mismo índice es cubriente: INCLUDE trae las columnas y PostgreSQL responde sin leer la tabla (Index Only Scan)",
        "tabla": "calculos",
    },
    {
        "nombre": "Estadística de un mes (panel del administrador)",
        "antes": """SELECT count(*), round(avg(paneles), 2), sum(ahorro_estimado_cop) FROM calculos
                    WHERE EXTRACT(YEAR FROM creado_en) = 2025 AND EXTRACT(MONTH FROM creado_en) = 6""",
        "despues": """SELECT count(*), round(avg(paneles), 2), sum(ahorro_estimado_cop) FROM calculos
                      WHERE creado_en >= '2025-06-01' AND creado_en < '2025-07-01'""",
        "cambio": "Rango sargable sobre creado_en + índice ix_calculos_creado_en",
        "tabla": "calculos",
    },
    {
        "nombre": "Cotizaciones pendientes más recientes",
        "antes": """SELECT id, calculo_id, precio_total, enviada_en FROM cotizaciones
                    WHERE estado_id = 1 ORDER BY enviada_en DESC LIMIT 20""",
        "despues": None,
        "cambio": "Índice compuesto ix_cotizaciones_estado_enviada (estado_id, enviada_en DESC)",
        "tabla": "cotizaciones",
    },
]


def migrar(url: str, destino: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", destino],
        cwd=RAIZ, env={"DATABASE_URL": url, "PATH": "/usr/bin:/bin"}, check=True, capture_output=True,
    )


def nodos(plan: dict) -> list[str]:
    tipo = plan["Node Type"] + (f" ({plan['Index Name']})" if "Index Name" in plan else "")
    return [tipo] + [n for hijo in plan.get("Plans", []) for n in nodos(hijo)]


def acceso(lista: list[str], tabla: str, plan: dict) -> str:
    def buscar(nodo):
        if "Scan" in nodo["Node Type"] and nodo.get("Relation Name") == tabla:
            indice = nodo.get("Index Name") or next((h.get("Index Name") for h in nodo.get("Plans", []) if h.get("Index Name")), None)
            return nodo["Node Type"] + (f" ({indice})" if indice else "")
        for hijo in nodo.get("Plans", []):
            encontrado = buscar(hijo)
            if encontrado:
                return encontrado
        return None
    return buscar(plan) or lista[0]


def miles(numero: float) -> str:
    return f"{numero:,.0f}".replace(",", ".")


def decimal(numero: float, cifras: int = 2) -> str:
    return f"{numero:.{cifras}f}".replace(".", ",")


def medir(cursor, consulta: str, tabla: str) -> dict:
    tiempos, plan = [], None
    for _ in range(REPETICIONES):
        cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + consulta)
        resultado = cursor.fetchone()[0][0]
        tiempos.append(resultado["Execution Time"])
        plan = resultado["Plan"]
    cursor.execute("EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) " + consulta)
    texto = "\n".join(f[0] for f in cursor.fetchall())
    return {
        "ms": statistics.median(tiempos),
        "acceso": acceso(nodos(plan), tabla, plan),
        "bloques": plan.get("Shared Hit Blocks", 0) + plan.get("Shared Read Blocks", 0),
        "texto": texto,
    }


def main(url: str) -> None:
    conexion = psycopg2.connect(url)
    conexion.autocommit = True
    cursor = conexion.cursor()
    cursor.execute("SELECT version_num FROM alembic_version")
    if cursor.fetchone()[0] != "0002_procedimientos_y_triggers":
        raise SystemExit("La base debe estar en la migración 0002 y con datos cargados (cargar_datos.sql)")
    cursor.execute("VACUUM ANALYZE")
    cursor.execute("SELECT (SELECT count(*) FROM usuarios), (SELECT count(*) FROM calculos), (SELECT count(*) FROM cotizaciones)")
    volumen = cursor.fetchone()

    antes = [medir(cursor, caso["antes"], caso["tabla"]) for caso in CASOS]
    migrar(url, "head")
    cursor.execute("VACUUM ANALYZE")
    despues = [medir(cursor, caso["despues"] or caso["antes"], caso["tabla"]) for caso in CASOS]
    suprimidos = [(caso, medir(cursor, caso["antes"], caso["tabla"])) for caso in CASOS if caso["despues"]]
    cursor.execute(
        "SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) FROM pg_stat_user_indexes "
        "WHERE indexrelname LIKE 'ix\\_%%' AND indexrelname IN ('ix_calculos_usuario_fecha', 'ix_calculos_creado_en', "
        "'ix_cotizaciones_estado_enviada', 'ix_calculos_ciudad_id') ORDER BY 1"
    )
    tamanos = cursor.fetchall()
    cursor.execute("SELECT version()")
    version = cursor.fetchone()[0].split(" on ")[0]
    conexion.close()

    lineas = [
        "# Resultados de optimización e indexación",
        "",
        f"Medido el {datetime.now():%Y-%m-%d %H:%M} con {version}. Volumen: {miles(volumen[0])} usuarios, "
        f"{miles(volumen[1])} cálculos y {miles(volumen[2])} cotizaciones (datos sintéticos de `cargar_datos.sql`). "
        f"Cada tiempo es la mediana de {REPETICIONES} ejecuciones de `EXPLAIN (ANALYZE, BUFFERS)`.",
        "",
        "| Consulta | Antes | Después | Mejora | Cambio aplicado |",
        "|---|---|---|---|---|",
    ]
    for caso, a, d in zip(CASOS, antes, despues):
        lineas.append(
            f"| {caso['nombre']} | {decimal(a['ms'])} ms · {a['acceso']} · {miles(a['bloques'])} bloques | "
            f"{decimal(d['ms'], 3)} ms · {d['acceso']} · {miles(d['bloques'])} bloques | "
            f"{miles(a['ms'] / d['ms'])}× | {caso['cambio']} |"
        )
    lineas += [
        "",
        "## Con el índice creado, la consulta no sargable sigue sin usarlo",
        "",
        "Se ejecutó de nuevo la versión original (con funciones sobre la columna) cuando los índices ya existían:",
        "",
        "| Consulta original | Tiempo | Acceso |",
        "|---|---|---|",
    ]
    lineas += [f"| {c['nombre']} | {decimal(m['ms'])} ms | {m['acceso']} |" for c, m in suprimidos]
    lineas += ["", "## Tamaño de los índices creados", "", "| Índice | Tamaño |", "|---|---|"]
    lineas += [f"| {n} | {t} |" for n, t in tamanos]
    lineas += ["", "## Planes de ejecución", ""]
    for caso, a, d in zip(CASOS, antes, despues):
        lineas += [f"### {caso['nombre']}", "", "**Antes**", "", "```sql", " ".join(caso["antes"].split()), "```", "", "```", a["texto"], "```", ""]
        lineas += ["**Después**", "", "```sql", " ".join((caso["despues"] or caso["antes"]).split()), "```", "", "```", d["texto"], "```", ""]
    (CARPETA / "resultados.md").write_text("\n".join(lineas), encoding="utf-8")
    print(json.dumps([{"caso": c["nombre"], "antes_ms": round(a["ms"], 2), "despues_ms": round(d["ms"], 3)} for c, a, d in zip(CASOS, antes, despues)], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
