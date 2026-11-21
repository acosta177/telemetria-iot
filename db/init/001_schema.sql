-- Se ejecuta al crear por primera vez el volumen de PostgreSQL.
--
-- REGLAS DE INTEGRIDAD (prueba E5). Se garantizan AQUI, en la base de datos,
-- y no solo en el codigo de los procesadores:
--   1. UNIQUE (sensor_id, ts): nunca hay dos lecturas del mismo sensor en el
--      mismo instante, aunque el cliente reintente o dos pods compitan.
--   2. La lectura y su alerta se guardan en UNA sola transaccion (ver
--      processor/main.py); la FK impide alertas huerfanas.
--   3. CHECK de rangos fisicos como ultima barrera.

CREATE TABLE IF NOT EXISTS lecturas (
    id              BIGSERIAL PRIMARY KEY,
    sensor_id       VARCHAR(32)  NOT NULL CHECK (sensor_id ~ '^[A-Za-z0-9_-]{3,32}$'),
    ts              TIMESTAMPTZ  NOT NULL,
    temperatura     NUMERIC(6,2) NOT NULL CHECK (temperatura BETWEEN -40 AND 125),
    consumo_w       NUMERIC(8,2) NOT NULL CHECK (consumo_w BETWEEN 0 AND 10000),
    promedio_movil  NUMERIC(6,2) NOT NULL,
    zscore          NUMERIC(8,2),
    severidad       VARCHAR(12)  CHECK (severidad IN ('CRITICA', 'ADVERTENCIA')),
    recibido_en     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT lecturas_sensor_ts_unico UNIQUE (sensor_id, ts)
);

CREATE TABLE IF NOT EXISTS alertas (
    id          BIGSERIAL PRIMARY KEY,
    sensor_id   VARCHAR(32)  NOT NULL,
    ts          TIMESTAMPTZ  NOT NULL,
    severidad   VARCHAR(12)  NOT NULL CHECK (severidad IN ('CRITICA', 'ADVERTENCIA')),
    motivo      VARCHAR(40)  NOT NULL,
    valor       NUMERIC(10,2) NOT NULL,
    creada_en   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT alertas_sensor_ts_unico UNIQUE (sensor_id, ts),
    CONSTRAINT alertas_lectura_fk FOREIGN KEY (sensor_id, ts)
        REFERENCES lecturas (sensor_id, ts) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alertas_creada_en ON alertas (creada_en DESC);
CREATE INDEX IF NOT EXISTS idx_alertas_severidad ON alertas (severidad);
