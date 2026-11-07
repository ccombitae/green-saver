INSERT INTO usuarios (nombre, email, telefono, password, rol, ciudad, consumo_mensual) VALUES
 ('Ana', 'Ana@Correo.com ', '300', '$2b$12$abc', 'user', 'Girardot', 250),
 ('Luis', 'luis@correo.com', '301', '$2b$12$def', 'user', 'Ciudad X', 0);
INSERT INTO calculos_sistema (email, consumption, estimatedPanels, coverage, estimatedSavings, recommendation) VALUES
 ('ana@correo.com', 250, 5, 98.5, 210000, 'Bien'),
 ('anonimo@correo.com', 100, 2, 90, 80000, 'x'),
 ('LUIS@correo.com', 300, 6, 100, 255000, 'y');
INSERT INTO cotizaciones (calculation_id, client_email, client_name, total_price, notes, materials, status, accepted_at, installation_date) VALUES
 (1, 'ana@correo.com', 'Ana', 12500000, 'n', '{"panelType":"Monocristalino 550W","inverterType":"Inversor Hibrido 5kW","batteryType":"Sin bateria","structureType":"Estructura coplanar aluminio"}', 'accepted', now(), '2026-11-15'),
 (3, 'luis@correo.com', 'Luis', 9000000, '', '{"panelType":"Panel Raro 450W","inverterType":"Inversor Hibrido 8kW","batteryType":"Bateria LiFePO4 5kWh","structureType":"Estructura suelo galvanizada"}', 'failed', NULL, NULL),
 (2, 'nadie@correo.com', 'Nadie', 1, '', '{}', 'sent', NULL, NULL);
INSERT INTO sistemas_instalados (usuario_id, system) VALUES
 (2, '{"capacity":"2,75 kWp","panels":"5 paneles","inverter":"Inversor Hibrido 5kW","battery":"Sin bateria","installDate":"2026-11-15","panelType":"Monocristalino 550W","sourceQuoteId":1}'),
 (3, '{"capacity":"","panels":"","inverter":"Inversor Marca Z","battery":"","installDate":"pronto"}');
