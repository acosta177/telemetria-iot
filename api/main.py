"""API publica: valida el formato de las lecturas y las envia al servicio de procesadores."""
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from shared.schemas import AlertaItem, Estadisticas, LecturaEntrada, LecturaSalida

PROCESSOR_URL = os.getenv("PROCESSOR_URL", "http://procesador:8001").rstrip("/")
# 0 = una conexion nueva por solicitud. Es deliberado: el Service de Kubernetes balancea
# por CONEXION, asi que con keep-alive las conexiones quedarian "pegadas" a los pods
# antiguos y los pods nuevos (E2) no recibirian trafico. Subirlo es un experimento extra.
KEEPALIVE = int(os.getenv("HTTP_KEEPALIVE", "0"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    limites = httpx.Limits(max_connections=200, max_keepalive_connections=KEEPALIVE)
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0), limits=limites) as cliente:
        app.state.cliente_procesadores = cliente
        yield


app = FastAPI(title="Telemetria IoT: API REST", version="1.0.0", lifespan=lifespan)


async def reenviar(metodo: str, ruta: str, cuerpo: dict | None = None,
                   params: dict | None = None) -> httpx.Response:
    try:
        return await app.state.cliente_procesadores.request(
            metodo, f"{PROCESSOR_URL}{ruta}", json=cuerpo, params=params)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(status_code=503, detail="Procesador temporalmente no disponible") from exc


def devolver(respuesta: httpx.Response) -> JSONResponse:
    try:
        contenido = respuesta.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Respuesta no valida del procesador")
    return JSONResponse(content=contenido, status_code=respuesta.status_code)


@app.get("/health/live")
def vivo():
    return {"estado": "vivo", "servicio": "api"}


@app.get("/health/ready")
def listo():
    return {"estado": "listo"}


@app.post("/api/v1/lecturas", responses={201: {"model": LecturaSalida}, 200: {"model": LecturaSalida}})
async def registrar_lectura(lectura: LecturaEntrada):
    """201 = lectura nueva guardada; 200 = reintento idempotente; 409 = mismo (sensor, ts) con otros valores."""
    r = await reenviar("POST", "/internal/lecturas", lectura.model_dump(mode="json"))
    return devolver(r)


@app.get("/api/v1/alertas", response_model=list[AlertaItem])
async def alertas(sensor_id: Optional[str] = None, severidad: Optional[str] = None,
                  limite: int = Query(50, ge=1, le=500)):
    params = {k: v for k, v in {"sensor_id": sensor_id, "severidad": severidad, "limite": limite}.items()
              if v is not None}
    return devolver(await reenviar("GET", "/internal/alertas", params=params))


@app.get("/api/v1/sensores/{sensor_id}/lecturas", response_model=list[LecturaSalida])
async def lecturas_de_sensor(sensor_id: str, limite: int = Query(20, ge=1, le=500)):
    return devolver(await reenviar("GET", f"/internal/sensores/{sensor_id}/lecturas",
                                   params={"limite": limite}))


@app.get("/api/v1/estadisticas", response_model=Estadisticas)
async def estadisticas():
    return devolver(await reenviar("GET", "/internal/estadisticas"))
