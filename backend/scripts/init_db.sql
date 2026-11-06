-- Se ejecuta una sola vez al crear el volumen de PostgreSQL (docker-entrypoint-initdb.d).
-- Alembic también la crea (IF NOT EXISTS), así que ambos caminos son seguros.
CREATE EXTENSION IF NOT EXISTS vector;
