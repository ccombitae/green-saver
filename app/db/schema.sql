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

CREATE TABLE IF NOT EXISTS cotizaciones (
    id SERIAL PRIMARY KEY,
    calculation_id INT NOT NULL,
    client_email VARCHAR(255) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    total_price NUMERIC(12, 2) NOT NULL,
    notes TEXT,
    materials JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'sent',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (calculation_id) REFERENCES calculos_sistema(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_calculos_email ON calculos_sistema(email);
CREATE INDEX IF NOT EXISTS idx_calculos_usuario_id ON calculos_sistema(usuario_id);
CREATE INDEX IF NOT EXISTS idx_calculos_created_at ON calculos_sistema(created_at);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_calculation_id ON cotizaciones(calculation_id);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_sent_at ON cotizaciones(sent_at);

INSERT INTO usuarios (nombre, email, telefono, password, rol, ciudad, consumo_mensual)
VALUES ('Administrador', 'admin@greensaver.com', '+34 000 000 000', 'admin', 'admin', 'Madrid', 0)
ON CONFLICT (email) DO NOTHING;
