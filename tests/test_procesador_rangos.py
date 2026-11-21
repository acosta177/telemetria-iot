"""El procesador rechaza rangos imposibles con 422 ANTES de tocar la base de datos."""
from fastapi.testclient import TestClient

from processor import main as proc


def datos(**cambios):
    d = {"sensor_id": "SENS-0001", "ts": "2026-11-19T12:00:00Z", "temperatura": 25.0, "consumo_w": 300.0}
    d.update(cambios)
    return d


def test_temperatura_imposible_422():
    r = TestClient(proc.app).post("/internal/lecturas", json=datos(temperatura=500))
    assert r.status_code == 422


def test_consumo_negativo_422():
    r = TestClient(proc.app).post("/internal/lecturas", json=datos(consumo_w=-5))
    assert r.status_code == 422
