-- Script de creación de tablas para la integración API

-- Tabla de usuarios actualizada para autenticación
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    telefono VARCHAR(20),
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(50) DEFAULT 'user',
    ciudad VARCHAR(255),
    consumo_mensual FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabla de cálculos actualizada para API JSON
CREATE TABLE IF NOT EXISTS calculos_sistema (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255),
    usuario_id INT,
    panel_id INT,
    inversor_id INT,
    bateria_id INT,
    consumption FLOAT,
    estimatedPanels INT,
    coverage FLOAT,
    estimatedSavings FLOAT,
    recommendation TEXT,
    paneles_necesarios INT,
    inversor_kw FLOAT,
    bateria_kwh FLOAT,
    costo_total FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- Tabla de proveedores (existente, asegurar que existe)
CREATE TABLE IF NOT EXISTS proveedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_empresa VARCHAR(255) NOT NULL,
    contacto VARCHAR(255),
    telefono VARCHAR(20),
    direccion VARCHAR(255),
    tipo_equipo VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de paneles (existente, asegurar que existe)
CREATE TABLE IF NOT EXISTS paneles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    modelo VARCHAR(255) NOT NULL,
    potencia_w FLOAT NOT NULL,
    precio FLOAT NOT NULL,
    proveedor_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
);

-- Tabla de inversores (existente, asegurar que existe)
CREATE TABLE IF NOT EXISTS inversores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    potencia_kw FLOAT NOT NULL,
    voltaje VARCHAR(50),
    precio FLOAT NOT NULL,
    proveedor_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
);

-- Tabla de baterías (existente, asegurar que existe)
CREATE TABLE IF NOT EXISTS baterias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    capacidad_kwh FLOAT NOT NULL,
    tipo VARCHAR(100),
    precio FLOAT NOT NULL,
    proveedor_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
);

-- ÍNDICES para mejorar performance
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_calculos_email ON calculos_sistema(email);
CREATE INDEX IF NOT EXISTS idx_calculos_usuario_id ON calculos_sistema(usuario_id);
CREATE INDEX IF NOT EXISTS idx_calculos_created_at ON calculos_sistema(created_at);

-- Insertar usuario administrador de prueba (opcional)
INSERT IGNORE INTO usuarios (nombre, email, telefono, password, rol, ciudad, consumo_mensual) 
VALUES ('Administrador', 'admin@greensaver.com', '+34 000 000 000', 'admin', 'admin', 'Madrid', 0);
