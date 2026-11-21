"""Logica pura: rangos, promedio movil, z-score y reglas de alerta (sin BD)."""
from shared import analitica as a


def test_rangos_validos():
    assert a.validar_rangos(25.0, 300.0) == []


def test_rangos_invalidos():
    assert len(a.validar_rangos(200.0, 300.0)) == 1
    assert len(a.validar_rangos(-50.0, -1.0)) == 2


def test_promedio_movil_incluye_lectura_actual():
    ev = a.evaluar(30.0, 300.0, [20.0, 20.0])
    assert ev["promedio_movil"] == round((20 + 20 + 30) / 3, 2)


def test_sin_historial_suficiente_no_hay_zscore():
    ev = a.evaluar(25.0, 300.0, [24.0, 25.0, 26.0])
    assert ev["zscore"] is None and ev["severidad"] is None


def test_temperatura_critica():
    ev = a.evaluar(90.0, 300.0, [])
    assert (ev["severidad"], ev["motivo"]) == ("CRITICA", "temperatura_critica")


def test_consumo_critico():
    ev = a.evaluar(25.0, 4500.0, [])
    assert (ev["severidad"], ev["motivo"]) == ("CRITICA", "consumo_critico")


def test_anomalia_por_zscore():
    previas = [25.0, 24.0, 26.0, 25.0, 25.5, 24.5, 25.0, 25.0, 24.8]
    ev = a.evaluar(50.0, 300.0, previas)
    assert ev["severidad"] == "ADVERTENCIA" and abs(ev["zscore"]) >= a.Z_UMBRAL


def test_lectura_normal_no_alerta():
    previas = [25.0, 24.0, 26.0, 25.0, 25.5, 24.5, 25.0, 25.0, 24.8]
    assert a.evaluar(25.3, 310.0, previas)["severidad"] is None


def test_critica_tiene_prioridad_sobre_anomalia():
    previas = [25.0] * 9
    assert a.evaluar(95.0, 300.0, previas)["severidad"] == "CRITICA"


def test_sensor_constante_no_dispara_falsa_anomalia():
    # sigma minima evita dividir entre ~0
    assert a.evaluar(25.4, 300.0, [25.0] * 9)["severidad"] is None
