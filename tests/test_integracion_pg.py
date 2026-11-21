"""Integracion contra PostgreSQL REAL (se omite si no hay BD).

Ejecutar con una BD que tenga db/init/001_schema.sql aplicado:
    TEST_PG_HOST=localhost TEST_PG_PASSWORD=... pytest tests/test_integracion_pg.py
Valida las reglas de integridad de E5 sin necesidad de Kubernetes.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

if not os.getenv("TEST_PG_HOST"):
    pytest.skip("Define TEST_PG_HOST para correr pruebas de integracion", allow_module_level=True)

os.environ["POSTGRES_HOST"] = os.environ["TEST_PG_HOST"]
os.environ["POSTGRES_DB"] = os.getenv("TEST_PG_DB", "telemetria")
os.environ["POSTGRES_USER"] = os.getenv("TEST_PG_USER", "iotuser")
os.environ["POSTGRES_PASSWORD"] = os.getenv("TEST_PG_PASSWORD", "")

from fastapi.testclient import TestClient  # noqa: E402

from processor import main as proc  # noqa: E402


@pytest.fixture(scope="module")
def cliente():
    with TestClient(proc.app) as c:
        yield c


def lectura(sensor, ts, temp=25.0, consumo=300.0):
    return {"sensor_id": sensor, "ts": ts, "temperatura": temp, "consumo_w": consumo}


def test_primera_201_y_reintento_200_sin_duplicar(cliente):
    s = f"IT-{uuid.uuid4().hex[:8]}"
    p = lectura(s, "2026-11-19T12:00:00.000001Z")
    assert cliente.post("/internal/lecturas", json=p).status_code == 201
    assert cliente.post("/internal/lecturas", json=p).status_code == 200
    assert len(cliente.get(f"/internal/sensores/{s}/lecturas").json()) == 1


def test_mismo_instante_con_otros_valores_409(cliente):
    s = f"IT-{uuid.uuid4().hex[:8]}"
    assert cliente.post("/internal/lecturas", json=lectura(s, "2026-11-19T12:00:00Z")).status_code == 201
    r = cliente.post("/internal/lecturas", json=lectura(s, "2026-11-19T12:00:00Z", temp=26.0))
    assert r.status_code == 409


def test_lectura_critica_guarda_alerta_en_la_misma_transaccion(cliente):
    s = f"IT-{uuid.uuid4().hex[:8]}"
    r = cliente.post("/internal/lecturas", json=lectura(s, "2026-11-19T12:00:00Z", temp=95.0))
    assert r.status_code == 201 and r.json()["alerta"]["severidad"] == "CRITICA"
    alertas = cliente.get("/internal/alertas", params={"sensor_id": s}).json()
    assert len(alertas) == 1 and alertas[0]["motivo"] == "temperatura_critica"
    # el reintento devuelve la misma alerta y NO crea otra
    r2 = cliente.post("/internal/lecturas", json=lectura(s, "2026-11-19T12:00:00Z", temp=95.0))
    assert r2.status_code == 200 and r2.json()["alerta"]["severidad"] == "CRITICA"
    assert len(cliente.get("/internal/alertas", params={"sensor_id": s}).json()) == 1


def test_concurrencia_misma_clave_genera_una_sola_fila(cliente):
    s = f"IT-{uuid.uuid4().hex[:8]}"
    p = lectura(s, "2026-11-19T12:00:00Z", temp=96.0)
    with ThreadPoolExecutor(max_workers=16) as ex:
        codigos = list(ex.map(lambda _: cliente.post("/internal/lecturas", json=p).status_code, range(40)))
    assert codigos.count(201) == 1 and codigos.count(200) == 39
    assert len(cliente.get(f"/internal/sensores/{s}/lecturas").json()) == 1
    assert len(cliente.get("/internal/alertas", params={"sensor_id": s}).json()) == 1


def test_promedio_movil_y_anomalia(cliente):
    s = f"IT-{uuid.uuid4().hex[:8]}"
    for i, t in enumerate([25.0, 24.0, 26.0, 25.0, 25.5, 24.5]):
        assert cliente.post("/internal/lecturas", json=lectura(s, f"2026-11-19T12:00:0{i}Z", temp=t)).status_code == 201
    r = cliente.post("/internal/lecturas", json=lectura(s, "2026-11-19T12:00:09Z", temp=55.0))
    assert r.json()["alerta"]["severidad"] == "ADVERTENCIA"
