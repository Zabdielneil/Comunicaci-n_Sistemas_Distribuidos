-- Inicialización de la base de datos del Sistema Distribuido de Consulta y Registro
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS registros (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dato            TEXT NOT NULL,
    origen_servidor VARCHAR(50) NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_registros_creado_en ON registros (creado_en DESC);
