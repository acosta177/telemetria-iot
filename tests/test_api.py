"""API sin PostgreSQL: validacion de formato y reenvio al procesador (simulado)."""
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import main as api_module
from shared.schemas import LecturaEntrada


def datos(**cambios):
    d = {"sensor_id": "SENS-0001", "ts": "2026-11-19T12:00:00.123456Z",
         "temperatura": 25.5, "consumo_w": 310.0}
    d.update(cambios)
    return d


def test_schema_rechaza_ts_sin_zona_horaria():
    with pytest.raises(ValidationError):
        LecturaEntrada(**datos(ts="2026-11-19T12:00:00"))


def test_schema_rechaza_sensor_id_invalido():
    with pytest.raises(ValidationError):
        LecturaEntrada(**datos(sensor_id="sensor con espacios"))


def test_schema_rechaza_campos_adicionales():
    with pytest.raises(ValidationError):
        LecturaEntrada(**datos(admin=True))


def test_schema_rechaza_nan():
    with pytest.raises(ValidationError):
        LecturaEntrada(**datos(temperatura=float("nan")))


def test_api_422_antes_de_contactar_procesador():
    c = TestClient(api_module.app)
    assert c.post("/api/v1/lecturas", json=datos(ts="no-es-fecha")).status_code == 422


def test_api_reenvia_y_conserva_201(monkeypatch):
    async def falso(metodo, ruta, cuerpo=None, params=None):
        assert (metodo, ruta) == ("POST", "/internal/lecturas")
        assert cuerpo["sensor_id"] == "SENS-0001"
        return httpx.Response(201, json={**cuerpo, "promedio_movil": 25.5, "zscore": None, "alerta": None})

    monkeypatch.setattr(api_module, "reenviar", falso)
    r = TestClient(api_module.app).post("/api/v1/lecturas", json=datos())
    assert r.status_code == 201 and r.json()["promedio_movil"] == 25.5


def test_api_conserva_409(monkeypatch):
    async def falso(metodo, ruta, cuerpo=None, params=None):
        return httpx.Response(409, json={"detail": "conflicto"})

    monkeypatch.setattr(api_module, "reenviar", falso)
    assert TestClient(api_module.app).post("/api/v1/lecturas", json=datos()).status_code == 409


def test_api_503_si_procesador_no_responde(monkeypatch):
    class Cliente:
        async def request(self, *a, **k):
            raise httpx.ConnectError("caido")

    api_module.app.state.cliente_procesadores = Cliente()
    r = TestClient(api_module.app).post("/api/v1/lecturas", json=datos())
    assert r.status_code == 503
