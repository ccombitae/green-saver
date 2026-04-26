CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    telefono VARCHAR(20),
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(50) DEFAULT 'user',
    ciudad VARCHAR(255),
    consumo_mensual NUMERIC(12, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calculos_sistema (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    usuario_id INT,
    panel_id INT,
    inversor_id INT,
    bateria_id INT,
    consumption NUMERIC(12, 2),
    estimatedPanels INT,
    coverage NUMERIC(12, 2),
    estimatedSavings NUMERIC(12, 2),
    recommendation TEXT,
    paneles_necesarios INT,
    inversor_kw NUMERIC(12, 2),
    bateria_kwh NUMERIC(12, 2),
    costo_total NUMERIC(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_calculos_email ON calculos_sistema(email);
CREATE INDEX IF NOT EXISTS idx_calculos_usuario_id ON calculos_sistema(usuario_id);
CREATE INDEX IF NOT EXISTS idx_calculos_created_at ON calculos_sistema(created_at);

INSERT INTO usuarios (nombre, email, telefono, password, rol, ciudad, consumo_mensual)
VALUES ('Administrador', 'admin@greensaver.com', '+34 000 000 000', 'admin', 'admin', 'Madrid', 0)
ON CONFLICT (email) DO NOTHING;
