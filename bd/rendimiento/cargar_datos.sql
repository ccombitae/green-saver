INSERT INTO usuarios (nombre, correo, telefono, contrasena_hash, ciudad_id, consumo_mensual_kwh, creado_en)
SELECT 'Usuario ' || g,
       'usuario' || g || '@prueba.com',
       '300' || lpad(g::text, 7, '0'),
       '$2b$12$cargadesintetica',
       (SELECT id FROM ciudades ORDER BY id OFFSET (g % 49) LIMIT 1),
       100 + (g % 400),
       timestamptz '2024-01-01' + (g % 1000) * interval '1 day'
FROM generate_series(1, 20000) AS g;

INSERT INTO calculos (usuario_id, ciudad_id, consumo_mensual_kwh, paneles, cobertura_pct, ahorro_estimado_cop, recomendacion, creado_en)
SELECT u.id,
       u.ciudad_id,
       100 + (g % 400),
       1 + (g % 12),
       60 + (g % 40),
       85000 + (g % 400) * 850,
       'Recomendación sintética ' || (g % 7),
       timestamptz '2024-01-01' + ((g::bigint * 7919) % (3 * 365 * 24 * 60)) * interval '1 minute'
FROM generate_series(1, 600000) AS g
JOIN usuarios u ON u.id = 1 + (g % 20000);

INSERT INTO cotizaciones (calculo_id, cliente_id, estado_id, precio_total, notas, enviada_en)
SELECT c.id,
       c.usuario_id,
       CASE WHEN g % 10 = 0 THEN 1 WHEN g % 10 = 1 THEN 3 ELSE 2 END,
       5000000 + (g % 100) * 100000,
       '',
       c.creado_en + interval '1 day'
FROM generate_series(1, 60000) AS g
JOIN calculos c ON c.id = g * 10;

ANALYZE;
