"""Procesador de telemetria: valida rangos, calcula promedio movil y z-score,
detecta anomalias y guarda lectura + alerta en UNA transaccion PostgreSQL.

Garantia de integridad (E5): la respuesta 200/201 se devuelve DESPUES del
COMMIT. Si el pod muere antes, el cliente no recibe confirmacion, reintenta con
el mismo (sensor_id, ts) y la restriccion UNIQUE evita duplicados.
"""
import os
from contextlib import asynccontextmanager
from datetime import timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from shared.analitica import HISTORIAL, evaluar, validar_rangos
from shared.schemas import AlertaItem, Estadisticas, LecturaEntrada, LecturaSalida

# Sin URI para que los caracteres especiales de la contrasena no se interpreten.
DB_OPTS = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "telemetria"),
    "user": os.getenv("POSTGRES_USER", "iotuser"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "connect_timeout": 3,
}
POOL = ConnectionPool(kwargs=DB_OPTS, min_size=1,
                      max_size=int(os.getenv("POOL_MAX", "8")), timeout=5, open=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    POOL.open(wait=False)
    yield
    POOL.close()


app = FastAPI(title="Procesador de telemetria (replicable)", version="1.0.0", lifespan=lifespan)


@app.get("/health/live")
def vivo():
    return {"estado": "vivo", "servicio": "procesador"}


@app.get("/health/ready")
def listo():
    try:
        with POOL.connection() as conn:
            conn.execute("SELECT 1")
        return {"estado": "listo", "base_de_datos": "conectada"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from exc


def a_respuesta(fila: dict, severidad: Optional[str], motivo: Optional[str],
                valor: Optional[float]) -> dict:
    alerta = None
    if severidad:
        alerta = {"severidad": severidad, "motivo": motivo, "valor": float(valor)}
    return {
        "sensor_id": fila["sensor_id"],
        "ts": fila["ts"].isoformat(),
        "temperatura": float(fila["temperatura"]),
        "consumo_w": float(fila["consumo_w"]),
        "promedio_movil": float(fila["promedio_movil"]),
        "zscore": None if fila["zscore"] is None else float(fila["zscore"]),
        "alerta": alerta,
    }


@app.post("/internal/lecturas", responses={201: {"model": LecturaSalida}, 200: {"model": LecturaSalida}})
def registrar_lectura(lectura: LecturaEntrada, response: Response):
    temperatura = round(lectura.temperatura, 2)
    consumo = round(lectura.consumo_w, 2)
    errores = validar_rangos(temperatura, consumo)
    if errores:
        raise HTTPException(status_code=422, detail=errores)
    ts = lectura.ts.astimezone(timezone.utc)

    try:
        # El bloque "with" es UNA transaccion: COMMIT al salir, ROLLBACK si hay excepcion.
        with POOL.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT temperatura FROM lecturas WHERE sensor_id = %s AND ts < %s "
                    "ORDER BY ts DESC LIMIT %s",
                    (lectura.sensor_id, ts, HISTORIAL),
                )
                previas = [float(f["temperatura"]) for f in cur.fetchall()]
                ev = evaluar(temperatura, consumo, previas)

                cur.execute(
                    """INSERT INTO lecturas
                         (sensor_id, ts, temperatura, consumo_w, promedio_movil, zscore, severidad)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (sensor_id, ts) DO NOTHING
                       RETURNING sensor_id, ts, temperatura, consumo_w, promedio_movil, zscore""",
                    (lectura.sensor_id, ts, temperatura, consumo,
                     ev["promedio_movil"], ev["zscore"], ev["severidad"]),
                )
                fila = cur.fetchone()
                if fila is not None:  # lectura nueva
                    if ev["severidad"]:
                        cur.execute(
                            "INSERT INTO alertas (sensor_id, ts, severidad, motivo, valor) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            (lectura.sensor_id, ts, ev["severidad"], ev["motivo"], ev["valor"]),
                        )
                    resultado = a_respuesta(fila, ev["severidad"], ev["motivo"], ev["valor"])
                    codigo = 201
                else:
                    # Reintento (o carrera con otro pod): se devuelve lo ya guardado.
                    cur.execute(
                        """SELECT l.sensor_id, l.ts, l.temperatura, l.consumo_w, l.promedio_movil,
                                  l.zscore, a.severidad, a.motivo, a.valor
                           FROM lecturas l
                           LEFT JOIN alertas a ON a.sensor_id = l.sensor_id AND a.ts = l.ts
                           WHERE l.sensor_id = %s AND l.ts = %s""",
                        (lectura.sensor_id, ts),
                    )
                    fila = cur.fetchone()
                    if fila is None:
                        raise HTTPException(status_code=503, detail="No se pudo consultar la lectura")
                    if float(fila["temperatura"]) != temperatura or float(fila["consumo_w"]) != consumo:
                        raise HTTPException(
                            status_code=409,
                            detail="Ya existe una lectura de ese sensor en ese instante con otros valores")
                    resultado = a_respuesta(fila, fila["severidad"], fila["motivo"], fila["valor"])
                    codigo = 200
        # Aqui el COMMIT ya ocurrio: recien ahora se confirma al cliente.
        response.status_code = codigo
        return resultado
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Persistencia temporalmente no disponible") from exc


@app.get("/internal/alertas", response_model=list[AlertaItem])
def listar_alertas(sensor_id: Optional[str] = None, severidad: Optional[str] = None,
                   limite: int = Query(50, ge=1, le=500)):
    try:
        with POOL.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT sensor_id, ts, severidad, motivo, valor::float8 AS valor, creada_en "
                    "FROM alertas WHERE (%s::text IS NULL OR sensor_id = %s) "
                    "AND (%s::text IS NULL OR severidad = %s) ORDER BY creada_en DESC LIMIT %s",
                    (sensor_id, sensor_id, severidad, severidad, limite),
                )
                return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Persistencia temporalmente no disponible") from exc


@app.get("/internal/sensores/{sensor_id}/lecturas", response_model=list[LecturaSalida])
def lecturas_de_sensor(sensor_id: str, limite: int = Query(20, ge=1, le=500)):
    try:
        with POOL.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """SELECT l.sensor_id, l.ts, l.temperatura::float8 AS temperatura,
                              l.consumo_w::float8 AS consumo_w, l.promedio_movil::float8 AS promedio_movil,
                              l.zscore::float8 AS zscore, a.severidad, a.motivo, a.valor::float8 AS valor
                       FROM lecturas l LEFT JOIN alertas a ON a.sensor_id = l.sensor_id AND a.ts = l.ts
                       WHERE l.sensor_id = %s ORDER BY l.ts DESC LIMIT %s""",
                    (sensor_id, limite),
                )
                salida = []
                for f in cur.fetchall():
                    alerta = None
                    if f["severidad"]:
                        alerta = {"severidad": f["severidad"], "motivo": f["motivo"], "valor": f["valor"]}
                    salida.append({k: f[k] for k in ("sensor_id", "ts", "temperatura", "consumo_w",
                                                     "promedio_movil", "zscore")} | {"alerta": alerta})
                return salida
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Persistencia temporalmente no disponible") from exc


@app.get("/internal/estadisticas", response_model=Estadisticas)
def estadisticas():
    try:
        with POOL.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT (SELECT COUNT(*) FROM lecturas)::integer AS total_lecturas, "
                    "(SELECT COUNT(DISTINCT sensor_id) FROM lecturas)::integer AS sensores, "
                    "(SELECT COUNT(*) FROM alertas WHERE severidad = 'CRITICA')::integer AS alertas_criticas, "
                    "(SELECT COUNT(*) FROM alertas WHERE severidad = 'ADVERTENCIA')::integer AS alertas_advertencia"
                )
                return cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Persistencia temporalmente no disponible") from exc
