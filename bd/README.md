# Green Saver · Programación y Administración de Bases de Datos

Este documento resume cómo se aplicaron a la base de datos de Green Saver los temas de la materia:
normalización, ORM, transacciones y concurrencia, optimización e indexación, procedimientos almacenados
y triggers, y NoSQL con arquitectura híbrida.

El motor relacional es **PostgreSQL 16**, que ya usa Green Saver en Azure. Las clases usaron MySQL (Sakila);
al final de cada sección se indica la equivalencia en MySQL.

| Tema | Dónde está |
|---|---|
| Modelo normalizado (3FN) | `app/db/modelos.py`, `app/db/migraciones/versiones/0001_esquema_normalizado.py`, `bd/diagramas/modelo_er.png` |
| ORM (SQLAlchemy 2.0) y conexión | `app/db/database.py`, `app/services/servicio_*.py` |
| Migraciones (Alembic) | `app/db/migraciones/`, `alembic.ini`, `app/db/migrar.py` |
| Procedimiento, triggers y función | `app/db/migraciones/versiones/0002_procedimientos_y_triggers.py` |
| Índices | `app/db/migraciones/versiones/0003_indices_optimizacion.py` |
| Medición con EXPLAIN ANALYZE | `bd/rendimiento/` (`cargar_datos.sql`, `medir.py`, `resultados.md`) |
| Demostraciones de concurrencia | `bd/demostraciones/concurrencia.py` y su salida `salida_concurrencia.txt` |
| MongoDB (arquitectura híbrida) | `app/db/documentos.py`, `app/routes/ml.py`, `bd/mongo/consultas.js` |
| Pruebas automatizadas | `tests/test_base_de_datos.py`, `tests/test_migracion_legado.py`, `tests/test_mongo.py`, `tests/test_sistema.py` |

El código nuevo no lleva comentarios y todos sus identificadores están en español. Las únicas palabras en inglés
son las de las librerías (`select`, `session`) y las llaves JSON que ya usan la app móvil y el sitio web
(`estimatedPanels`, `clientEmail`): se conservaron para no romper esos dos clientes.

---

## 1. Normalización

### Problemas del modelo anterior

| Tabla | Problema | Forma normal que incumplía |
|---|---|---|
| `cotizaciones` | `materials` guardaba un JSON con cuatro equipos en una sola columna | 1FN: atributo no atómico, grupo repetido |
| `sistemas_instalados` | `system` guardaba todo el sistema como JSON (capacidad, paneles, inversor, batería y fecha como texto) | 1FN |
| `calculos_sistema` | guardaba `email` y además `usuario_id`; el correo depende del usuario, no del cálculo | 3FN: dependencia transitiva `id → usuario_id → email` |
| `cotizaciones` | `client_email` y `client_name` repetían datos del usuario | 3FN |
| `calculos_sistema` | columnas duplicadas (`estimatedPanels` y `paneles_necesarios`) y `panel_id`, `inversor_id`, `bateria_id` sin tabla a la cual apuntar | redundancia y llaves foráneas inexistentes |
| `usuarios` | `ciudad` y `rol` como texto libre; las 49 ciudades del modelo solo existían en un CSV | sin catálogo ni integridad referencial |
| `cotizaciones` | `status` como texto libre y `installation_date` como `VARCHAR` | dominio no controlado |
| Todas | nombres en español e inglés mezclados (`consumption`, `calculation_id`, `nombre`) | — |

### Modelo nuevo

![Modelo entidad-relación](diagramas/modelo_er.png)

- **1FN.** Los JSON se reemplazaron por tablas de detalle con llave primaria compuesta:
  - `detalle_cotizacion (cotizacion_id, equipo_id)`;
  - `equipos_sistema (sistema_id, equipo_id)`.

  Cada equipo es una fila con su cantidad.
- **2FN.** En las tablas con llave compuesta, cada atributo depende de la llave completa.
  - `cantidad` y `precio_unitario_cop` dependen del par cotización-equipo.
  - El nombre y la potencia del equipo viven en `equipos`.
- **3FN.** Se quitaron las dependencias transitivas:
  - el cálculo y la cotización apuntan al usuario (`usuario_id`, `cliente_id`), y el correo y el nombre se obtienen con un JOIN;
  - la ciudad apunta a `ciudades`, y la ciudad apunta a `departamentos`.
- **Catálogos.** `roles`, `estados_cotizacion`, `tipos_equipo`, `equipos`, `ciudades` y `departamentos` reemplazan el texto libre.
- **Restricciones.**
  - `CHECK` en cantidades, precios, consumo y cobertura (no negativos).
  - El correo debe guardarse en minúsculas (`correo = lower(btrim(correo))`).
  - `estimacion_id` debe ser un ObjectId de MongoDB válido.
- **Reglas de borrado.**

  | Si se elimina… | Efecto | Regla |
  |---|---|---|
  | un usuario | sus cálculos quedan para las estadísticas | `SET NULL` |
  | un usuario | se borran su sistema y sus cotizaciones | `CASCADE` |
  | un equipo usado en una cotización | el borrado se rechaza | `RESTRICT` |

- **Precio histórico.** `detalle_cotizacion.precio_unitario_cop` copia el precio del catálogo al cotizar. Así la
  cotización no cambia si después se actualiza el precio del equipo; es la regla del ejemplo de la clase 3.

### Migración de los datos existentes

La migración `0001` revisa si la base tiene las tablas viejas (`calculos_sistema`). Si las tiene:

1. las mueve al esquema `legado`, sin borrarlas;
2. crea el modelo nuevo y carga los catálogos;
3. copia los datos.

En la copia:
- normaliza los correos;
- une cada cálculo con su usuario por correo;
- convierte el JSON de materiales en filas de `detalle_cotizacion`;
- convierte el texto del sistema instalado (por ejemplo, "2,75 kWp") en `potencia_kwp`.

`tests/test_migracion_legado.py` comprueba este proceso con datos de ejemplo.

Una cotización cuyo correo no corresponde a ningún usuario registrado no se migra, porque en el modelo nuevo toda
cotización necesita un cliente. Esa fila sigue disponible en `legado.cotizaciones`.

---

## 2. ORM: SQLAlchemy 2.0

- **Mapeo.** Cada tabla es una clase en `app/db/modelos.py` (`Usuario`, `Calculo`, `Cotizacion`…), con `Mapped[...]`, llaves foráneas y relaciones.
- **Conexión y pool.** En `app/db/database.py`:

  ```python
  create_engine(url, pool_size=5, max_overflow=5, pool_timeout=10, pool_recycle=1800, pool_pre_ping=True)
  ```

  `pool_pre_ping` descarta conexiones que Azure cerró. `pool_recycle` las renueva cada 30 minutos.
- **Transacciones.** `sesion_transaccional()` abre `Session.begin()`: hace COMMIT si el bloque termina bien y ROLLBACK si hay una excepción.
- **Consultas parametrizadas.** El ORM nunca concatena valores dentro del SQL, lo que evita la inyección SQL.
- **Problema N+1.** Se evita con:
  - `lazy="joined"` para relaciones de uno, como el rol del usuario o el estado de la cotización;
  - `lazy="selectin"` para listas, como el detalle de una cotización (una sola consulta extra con `IN`).
- **Migraciones.** Se usa Alembic.
  - `alembic upgrade head` deja la base en la última versión.
  - Al arrancar, la API aplica las migraciones pendientes si `INIT_DB=true`. Usa `pg_advisory_lock` para que dos procesos de Gunicorn no migren al mismo tiempo.
  - `alembic check` confirma que los modelos y las migraciones coinciden.

Equivalencia en MySQL: el mismo código funciona con `mysql+pymysql://...`. Habría que cambiar el procedimiento y
los triggers, que están escritos en PL/pgSQL.

---

## 3. Transacciones y concurrencia

| Caso | Mecanismo | Dónde |
|---|---|---|
| Enviar cotización: la cotización y sus líneas de detalle se guardan juntas o no se guarda nada | Transacción del ORM (atomicidad) | `servicio_cotizaciones.registrar_cotizacion` |
| Dos administradores aceptan la misma cotización al mismo tiempo (como el reto del "último boleto") | Bloqueo pesimista `SELECT … FOR UPDATE` dentro del procedimiento | `aceptar_cotizacion` |
| Dos administradores editan el mismo usuario | Bloqueo optimista con columna `version` (`version_id_col` del ORM); la API responde **409** | `servicio_usuarios.actualizar_usuario` |
| Lectura no repetible | Nivel de aislamiento `REPEATABLE READ` | Prueba y demostración |

Salida real de `python bd/demostraciones/concurrencia.py <url>`:

```
=== 1. Dos sesiones suman 50 kWh al mismo usuario (SIN BLOQUEO) ===
Resultado final: 150.00 (esperado 200) -> ¡se perdió una actualización!
=== 1. Dos sesiones suman 50 kWh al mismo usuario (CON SELECT ... FOR UPDATE) ===
Resultado final: 200.00 (esperado 200) -> correcto
=== 2. Dos administradores aceptan la misma cotización ===
Admin B   ERROR -> La cotización 1 ya fue aceptada (ROLLBACK)
=== 3. Lectura no repetible según el nivel de aislamiento ===
READ COMMITTED   primera lectura = 200.00, segunda lectura = 201.00 -> lectura no repetible
REPEATABLE READ  primera lectura = 201.00, segunda lectura = 201.00 -> la transacción ve una foto estable
```

**Diferencias con MySQL que conviene saber:**
- **Nivel por defecto.** En PostgreSQL es `READ COMMITTED`; en MySQL InnoDB es `REPEATABLE READ`.
- **Lecturas sucias.** PostgreSQL nunca las permite: si se pide `READ UNCOMMITTED`, se comporta como `READ COMMITTED`.
- **MVCC.** Ambos motores lo usan: los lectores no bloquean a los escritores.

---

## 4. Procedimiento almacenado, triggers y función

| Objeto | Tipo | Qué hace |
|---|---|---|
| `aceptar_cotizacion(id, fecha, INOUT sistema_id)` | Procedimiento (`CALL`) | Bloquea la cotización (`FOR UPDATE`), valida que exista y que no esté aceptada, la marca como aceptada, crea o actualiza el sistema instalado y copia los equipos. Si algo falla, el bloque `EXCEPTION` revierte todo y devuelve un mensaje claro |
| `trg_cotizaciones_validar` | Trigger `BEFORE INSERT OR UPDATE` | Una cotización aceptada debe tener fecha de instalación, no anterior al envío, y no puede volver a otro estado |
| `trg_cotizaciones_auditar` | Trigger `AFTER INSERT OR UPDATE OF estado_id` | Registra cada cambio de estado en `auditoria_cotizaciones` |
| `trg_usuarios_actualizado_en`, `trg_sistemas_actualizado_en` | Trigger `BEFORE UPDATE` | Mantienen `actualizado_en` |
| `fn_estadisticas_mensuales(desde, hasta)` | Función que devuelve una tabla | Cálculos, paneles promedio y ahorro por mes; la usa `GET /calculos/estadisticas` |

Como concluyó la exposición del PDF, el trigger complementa la transacción pero no la reemplaza: la auditoría la
hace el trigger, y la atomicidad la da el procedimiento.

| MySQL (clase) | PostgreSQL (Green Saver) |
|---|---|
| `DELIMITER //` | Cuerpo entre `$$ … $$` |
| `DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; … END` | Bloque `BEGIN … EXCEPTION WHEN … THEN … END`: al entrar al `EXCEPTION`, PostgreSQL revierte todo lo hecho en el bloque |
| `SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '…'` | `RAISE EXCEPTION '…' USING ERRCODE = 'check_violation'` |
| Parámetro `OUT` | Parámetro `INOUT` en procedimientos |
| `START TRANSACTION … COMMIT` dentro del procedimiento | La transacción la abre quien llama: el ORM hace COMMIT o ROLLBACK |

---

## 5. Optimización e indexación

Se cargaron 20.000 usuarios, 600.000 cálculos y 60.000 cotizaciones sintéticos (`bd/rendimiento/cargar_datos.sql`).
Luego se midió con `EXPLAIN (ANALYZE, BUFFERS)` antes y después de la migración `0003`. Los resultados completos,
con los planes de ejecución, están en [`rendimiento/resultados.md`](rendimiento/resultados.md).

| Consulta | Antes | Después | Mejora |
|---|---|---|---|
| Historial de un usuario | 35,16 ms · Seq Scan | 0,036 ms · índice `ix_calculos_usuario_fecha` | 977× |
| Inicio de sesión por correo | 3,88 ms · Seq Scan | 0,004 ms · Index Scan | 970× |
| Resumen de ahorro de un usuario | 14,07 ms · Seq Scan | 0,013 ms · **Index Only Scan** (índice cubriente) | 1.083× |
| Estadística de un mes | 58,18 ms · Seq Scan | 4,70 ms · Bitmap Heap Scan | 12× |
| Cotizaciones pendientes más recientes | 2,71 ms · Seq Scan | 0,012 ms · Index Scan | 226× |

**Índice compuesto y prefijo izquierdo.** `ix_calculos_usuario_fecha (usuario_id, creado_en DESC)` sirve para:
- filtrar por usuario;
- entregar los cálculos ya ordenados;
- consultas solo por `usuario_id`, gracias al prefijo izquierdo.

**Índice cubriente.** Con `INCLUDE (consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop)`, el resumen
del usuario se responde sin leer la tabla (`Index Only Scan`, 4 bloques en lugar de 8.000).

**Consultas sargables.** Hay dos casos:
- El código anterior buscaba con `lower(email) = lower(…)`, que obliga a recorrer la tabla. Ahora el correo se guarda normalizado (lo exige un `CHECK`) y se compara directo.
- La estadística usaba `EXTRACT(YEAR FROM creado_en) = 2025`. Ahora usa el rango `creado_en >= '2025-06-01' AND creado_en < '2025-07-01'`.

Con los índices ya creados, las versiones con funciones siguieron haciendo `Seq Scan`. Es el mismo fenómeno de la
exposición del Grupo 2: el índice existe, pero el motor no puede usarlo.

**Costo de los índices.** Ocupan 34 MB (`ix_calculos_usuario_fecha`) y 13 MB (`ix_calculos_creado_en`) para
600.000 cálculos, y hacen un poco más lentas las inserciones. Se justifican porque las lecturas son mucho más
frecuentes que las escrituras.

**Índices en llaves foráneas.** PostgreSQL no indexa las llaves foráneas automáticamente. Por eso se crearon índices
en `cotizaciones.calculo_id`, `cotizaciones.cliente_id`, `detalle_cotizacion.equipo_id` y otras: sin ellos, cada
`DELETE … CASCADE` recorrería la tabla hija completa.

**Para repetir la medición:**

```bash
DATABASE_URL=postgresql://usuario:clave@localhost:5432/gs_rendimiento alembic upgrade 0002_procedimientos_y_triggers
psql -d gs_rendimiento -v ON_ERROR_STOP=1 -f bd/rendimiento/cargar_datos.sql
python bd/rendimiento/medir.py postgresql://usuario:clave@localhost:5432/gs_rendimiento
```

En un servidor real, el equivalente al *slow query log* de MySQL es `log_min_duration_statement` o la extensión
`pg_stat_statements`.

---

## 6. NoSQL: MongoDB y arquitectura híbrida

**Qué va en cada motor (un dato, un solo dueño):**
- **PostgreSQL** guarda lo que exige integridad y ACID: usuarios, cálculos guardados, cotizaciones con dinero, sistemas instalados y auditoría.
- **MongoDB** guarda el resultado completo de cada estimación, colección `estimaciones`. Incluye las que hacen personas sin cuenta en la calculadora pública.
  - Es un documento grande y anidado: 12 meses, equipos, baterías, instalación y desglose de costos.
  - Su forma cambia cuando el modelo agrega datos nuevos.
  - Siempre se lee completo.

  Normalizarlo en SQL exigiría varias tablas y JOINs para algo que nunca se consulta por partes.

**Enlace entre los dos motores:**
- `POST /ml/estimar` guarda el documento y devuelve `estimacion_id`.
- Si el cliente envía ese id en `estimationId` al guardar el cálculo, queda en `calculos.estimacion_id` (validado con un `CHECK`).

```json
{
  "_id": "6aeec69818d7c11a2e208d90",
  "creado_en": "2026-11-07T06:35:04Z",
  "usuario": "ana@correo.com",
  "ciudad": { "id": "girardot", "nombre": "Girardot", "departamento": "Cundinamarca", "latitud": 4.3032 },
  "solicitud": { "consumo_mensual_kwh": 250, "ciudad_id": "girardot", "potencia_panel_w": 550, "tarifa_kwh_cop": 850 },
  "resumen": { "paneles": 5, "potencia_kwp": 2.75, "cobertura_anual_pct": 100.0, "ahorro_anual_cop": 2550000, "costo_total_cop": 8136363 },
  "detalle_mensual": [ { "mes": "Ene", "hsp": 4.87, "generacion_kwh": 332.2, "cobertura_pct": 100.0 }, "…" ],
  "equipos": { "inversor": { "potencia_kw": 3 }, "baterias": { }, "instalacion": { } },
  "costos": { "total_cop": 8136363, "detalle": [ ] }
}
```

**Índices de la colección:**
- `ix_ciudad_fecha (ciudad.id, creado_en desc)`;
- `ix_fecha`;
- `ix_usuario_fecha` (disperso).

Una prueba verifica con `explain()` que la consulta por ciudad use `ix_ciudad_fecha`.

**Endpoints nuevos:**

| Endpoint | Para quién | Qué hace |
|---|---|---|
| `GET /ml/estimaciones` | Usuario o administrador | Estimaciones recientes; el usuario ve solo las suyas |
| `GET /ml/estimaciones/{id}` | Usuario o administrador | El documento completo |
| `GET /ml/estimaciones/estadisticas` | Administrador | Agregación `$group` por ciudad: estimaciones, consumo, paneles y costo promedio |

Más consultas para `mongosh` en [`mongo/consultas.js`](mongo/consultas.js): filtro dentro de arreglos con
`$elemMatch` y `$unwind` de los meses.

**Si MongoDB falla,** la estimación sigue funcionando y `estimacion_id` llega en `null`. La disponibilidad del
servicio principal no depende de la base documental.

**Configuración:** variables `MONGO_URL` y `MONGO_BD` (por defecto `green_saver`). Opciones gratuitas para la nube:
- MongoDB Atlas, clúster M0;
- Azure Cosmos DB for MongoDB, con su nivel gratuito en la suscripción de estudiante.

---

## 7. Pruebas

```bash
export TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/greensaver_test
export MONGO_URL_PRUEBAS=mongodb://localhost:27017
python -m pytest -q
```

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `test_base_de_datos.py` | 15 | `CHECK`, llaves foráneas, triggers de validación y auditoría, el procedimiento (y que revierte todo si falla), dos administradores en paralelo, bloqueo optimista y respuesta 409, niveles de aislamiento, atomicidad de la cotización y la función de estadísticas |
| `test_migracion_legado.py` | 7 | Que los datos del modelo anterior lleguen bien al nuevo |
| `test_mongo.py` | 6 | Documento guardado, agregación por ciudad, uso del índice y funcionamiento sin MongoDB |
| `test_sistema.py` | 18 | El flujo completo de la API con la base nueva, sin cambios para la app y la web |
| Resto | 48 | Pruebas unitarias y de API que ya existían |

**Total:** 94 pruebas, todas aprobadas. En GitHub Actions corren con PostgreSQL 16 y MongoDB 7 como servicios, antes de cada despliegue.

---

## 8. Cambios en la API

**Lo que no cambia:**
- Las respuestas que usan la app y la web son las mismas.

**Lo que se agregó:**
- `estimacion_id` en `POST /ml/estimar`.
- `cityId` y `estimationId` opcionales en `POST /calculos`.
- `GET /calculos/estadisticas`.
- Los endpoints de `/ml/estimaciones`.

**Defectos que salieron a la luz con el modelo nuevo:**
- `POST /calculos` tomaba el correo del cuerpo de la petición: un usuario podía guardar cálculos a nombre de otro. Ahora usa el correo del token (el administrador sí puede indicarlo).
- `DELETE /calculos/{id}` permitía a cualquier usuario borrar cualquier cálculo. Ahora es solo para el administrador.

**Lo que se retiró por inconsistente con el modelo:**
- `POST /usuarios`: creaba usuarios sin correo ni contraseña; ningún cliente lo usaba.
- `PUT /calculos/{id}`: escribía columnas que no correspondían a nada.

**Comportamientos nuevos:**
- Una cotización solo se puede enviar a un cliente registrado.
- La fecha de instalación debe tener formato AAAA-MM-DD.

---

## 9. Despliegue

Al unir esta rama a `main`, el flujo de GitHub Actions publica la API, y Azure aplica las migraciones al arrancar
(`INIT_DB=true`). La migración `0001` mueve las tablas actuales al esquema `legado` y copia sus datos al modelo nuevo.

**Antes de unir la rama:**
1. Sacar un respaldo de la base de Azure.
2. Probar la migración sobre una copia de esa base.
