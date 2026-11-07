# Resultados de optimización e indexación

Medido el 2026-11-07 01:32 con PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1). Volumen: 20.000 usuarios, 600.000 cálculos y 60.000 cotizaciones (datos sintéticos de `cargar_datos.sql`). Cada tiempo es la mediana de 7 ejecuciones de `EXPLAIN (ANALYZE, BUFFERS)`.

| Consulta | Antes | Después | Mejora | Cambio aplicado |
|---|---|---|---|---|
| Historial de un usuario (GET /calculos) | 35,16 ms · Seq Scan · 8.121 bloques | 0,036 ms · Bitmap Heap Scan (ix_calculos_usuario_fecha) · 36 bloques | 977× | Índice compuesto ix_calculos_usuario_fecha (usuario_id, creado_en DESC): filtra y entrega el orden |
| Inicio de sesión: búsqueda por correo | 3,88 ms · Seq Scan · 345 bloques | 0,004 ms · Index Scan (usuarios_correo_key) · 3 bloques | 970× | Consulta sargable: el correo se guarda normalizado (CHECK) y se compara sin funciones sobre la columna |
| Resumen de ahorro de un usuario | 14,07 ms · Seq Scan · 8.000 bloques | 0,013 ms · Index Only Scan (ix_calculos_usuario_fecha) · 4 bloques | 1.083× | El mismo índice es cubriente: INCLUDE trae las columnas y PostgreSQL responde sin leer la tabla (Index Only Scan) |
| Estadística de un mes (panel del administrador) | 58,18 ms · Seq Scan · 8.000 bloques | 4,702 ms · Bitmap Heap Scan (ix_calculos_creado_en) · 3.237 bloques | 12× | Rango sargable sobre creado_en + índice ix_calculos_creado_en |
| Cotizaciones pendientes más recientes | 2,71 ms · Seq Scan · 561 bloques | 0,012 ms · Index Scan (ix_cotizaciones_estado_enviada) · 23 bloques | 226× | Índice compuesto ix_cotizaciones_estado_enviada (estado_id, enviada_en DESC) |

## Con el índice creado, la consulta no sargable sigue sin usarlo

Se ejecutó de nuevo la versión original (con funciones sobre la columna) cuando los índices ya existían:

| Consulta original | Tiempo | Acceso |
|---|---|---|
| Inicio de sesión: búsqueda por correo | 3,84 ms | Seq Scan |
| Estadística de un mes (panel del administrador) | 58,33 ms | Seq Scan |

## Tamaño de los índices creados

| Índice | Tamaño |
|---|---|
| ix_calculos_ciudad_id | 4096 kB |
| ix_calculos_creado_en | 13 MB |
| ix_calculos_usuario_fecha | 34 MB |
| ix_cotizaciones_estado_enviada | 1872 kB |

## Planes de ejecución

### Historial de un usuario (GET /calculos)

**Antes**

```sql
SELECT c.id, c.consumo_mensual_kwh, c.paneles, c.cobertura_pct, c.ahorro_estimado_cop, c.creado_en FROM calculos c JOIN usuarios u ON u.id = c.usuario_id WHERE u.correo = 'usuario4321@prueba.com' ORDER BY c.creado_en DESC
```

```
Gather Merge (actual rows=30 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=8121
  ->  Sort (actual rows=10 loops=3)
        Sort Key: c.creado_en DESC
        Sort Method: quicksort  Memory: 26kB
        Buffers: shared hit=8121
        Worker 0:  Sort Method: quicksort  Memory: 25kB
        Worker 1:  Sort Method: quicksort  Memory: 25kB
        ->  Hash Join (actual rows=10 loops=3)
              Hash Cond: (c.usuario_id = u.id)
              Buffers: shared hit=8105
              ->  Parallel Seq Scan on calculos c (actual rows=200000 loops=3)
                    Buffers: shared hit=8000
              ->  Hash (actual rows=1 loops=3)
                    Buckets: 1024  Batches: 1  Memory Usage: 9kB
                    Buffers: shared hit=11
                    ->  Index Scan using usuarios_correo_key on usuarios u (actual rows=1 loops=3)
                          Index Cond: ((correo)::text = 'usuario4321@prueba.com'::text)
                          Buffers: shared hit=11
Planning:
  Buffers: shared hit=6
```

**Después**

```sql
SELECT c.id, c.consumo_mensual_kwh, c.paneles, c.cobertura_pct, c.ahorro_estimado_cop, c.creado_en FROM calculos c JOIN usuarios u ON u.id = c.usuario_id WHERE u.correo = 'usuario4321@prueba.com' ORDER BY c.creado_en DESC
```

```
Sort (actual rows=30 loops=1)
  Sort Key: c.creado_en DESC
  Sort Method: quicksort  Memory: 26kB
  Buffers: shared hit=36
  ->  Nested Loop (actual rows=30 loops=1)
        Buffers: shared hit=36
        ->  Index Scan using usuarios_correo_key on usuarios u (actual rows=1 loops=1)
              Index Cond: ((correo)::text = 'usuario4321@prueba.com'::text)
              Buffers: shared hit=3
        ->  Bitmap Heap Scan on calculos c (actual rows=30 loops=1)
              Recheck Cond: (usuario_id = u.id)
              Heap Blocks: exact=30
              Buffers: shared hit=33
              ->  Bitmap Index Scan on ix_calculos_usuario_fecha (actual rows=30 loops=1)
                    Index Cond: (usuario_id = u.id)
                    Buffers: shared hit=3
Planning:
  Buffers: shared hit=14
```

### Inicio de sesión: búsqueda por correo

**Antes**

```sql
SELECT id, contrasena_hash FROM usuarios WHERE lower(correo) = lower('Usuario4321@Prueba.com')
```

```
Seq Scan on usuarios (actual rows=1 loops=1)
  Filter: (lower((correo)::text) = 'usuario4321@prueba.com'::text)
  Rows Removed by Filter: 19999
  Buffers: shared hit=345
```

**Después**

```sql
SELECT id, contrasena_hash FROM usuarios WHERE correo = 'usuario4321@prueba.com'
```

```
Index Scan using usuarios_correo_key on usuarios (actual rows=1 loops=1)
  Index Cond: ((correo)::text = 'usuario4321@prueba.com'::text)
  Buffers: shared hit=3
```

### Resumen de ahorro de un usuario

**Antes**

```sql
SELECT count(*), sum(ahorro_estimado_cop), round(avg(paneles), 2) FROM calculos WHERE usuario_id = 4321
```

```
Finalize Aggregate (actual rows=1 loops=1)
  Buffers: shared hit=8000
  ->  Gather (actual rows=3 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=8000
        ->  Partial Aggregate (actual rows=1 loops=3)
              Buffers: shared hit=8000
              ->  Parallel Seq Scan on calculos (actual rows=10 loops=3)
                    Filter: (usuario_id = 4321)
                    Rows Removed by Filter: 199990
                    Buffers: shared hit=8000
```

**Después**

```sql
SELECT count(*), sum(ahorro_estimado_cop), round(avg(paneles), 2) FROM calculos WHERE usuario_id = 4321
```

```
Aggregate (actual rows=1 loops=1)
  Buffers: shared hit=4
  ->  Index Only Scan using ix_calculos_usuario_fecha on calculos (actual rows=30 loops=1)
        Index Cond: (usuario_id = 4321)
        Heap Fetches: 0
        Buffers: shared hit=4
```

### Estadística de un mes (panel del administrador)

**Antes**

```sql
SELECT count(*), round(avg(paneles), 2), sum(ahorro_estimado_cop) FROM calculos WHERE EXTRACT(YEAR FROM creado_en) = 2025 AND EXTRACT(MONTH FROM creado_en) = 6
```

```
Finalize Aggregate (actual rows=1 loops=1)
  Buffers: shared hit=8000
  ->  Gather (actual rows=3 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=8000
        ->  Partial Aggregate (actual rows=1 loops=3)
              Buffers: shared hit=8000
              ->  Parallel Seq Scan on calculos (actual rows=5478 loops=3)
                    Filter: ((EXTRACT(year FROM creado_en) = '2025'::numeric) AND (EXTRACT(month FROM creado_en) = '6'::numeric))
                    Rows Removed by Filter: 194522
                    Buffers: shared hit=8000
```

**Después**

```sql
SELECT count(*), round(avg(paneles), 2), sum(ahorro_estimado_cop) FROM calculos WHERE creado_en >= '2025-06-01' AND creado_en < '2025-07-01'
```

```
Aggregate (actual rows=1 loops=1)
  Buffers: shared hit=3237
  ->  Bitmap Heap Scan on calculos (actual rows=16434 loops=1)
        Recheck Cond: ((creado_en >= '2025-06-01 00:00:00-05'::timestamp with time zone) AND (creado_en < '2025-07-01 00:00:00-05'::timestamp with time zone))
        Heap Blocks: exact=3189
        Buffers: shared hit=3237
        ->  Bitmap Index Scan on ix_calculos_creado_en (actual rows=16434 loops=1)
              Index Cond: ((creado_en >= '2025-06-01 00:00:00-05'::timestamp with time zone) AND (creado_en < '2025-07-01 00:00:00-05'::timestamp with time zone))
              Buffers: shared hit=48
```

### Cotizaciones pendientes más recientes

**Antes**

```sql
SELECT id, calculo_id, precio_total, enviada_en FROM cotizaciones WHERE estado_id = 1 ORDER BY enviada_en DESC LIMIT 20
```

```
Limit (actual rows=20 loops=1)
  Buffers: shared hit=561
  ->  Sort (actual rows=20 loops=1)
        Sort Key: enviada_en DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=561
        ->  Seq Scan on cotizaciones (actual rows=6000 loops=1)
              Filter: (estado_id = 1)
              Rows Removed by Filter: 54000
              Buffers: shared hit=561
```

**Después**

```sql
SELECT id, calculo_id, precio_total, enviada_en FROM cotizaciones WHERE estado_id = 1 ORDER BY enviada_en DESC LIMIT 20
```

```
Limit (actual rows=20 loops=1)
  Buffers: shared hit=23
  ->  Index Scan using ix_cotizaciones_estado_enviada on cotizaciones (actual rows=20 loops=1)
        Index Cond: (estado_id = 1)
        Buffers: shared hit=23
```
