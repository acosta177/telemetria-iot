"""Logica pura de analitica de telemetria (sin base de datos, facil de probar).

Reglas (documentadas tambien en docs/ARQUITECTURA.md):
  * Rangos fisicos validos: temperatura -40..125 C, consumo 0..10000 W.
  * Promedio movil: media de las ultimas VENTANA lecturas de temperatura del
    sensor, INCLUYENDO la actual.
  * Z-score: cuantas desviaciones estandar se aleja la lectura actual de las
    VENTANA-1 lecturas previas (solo si hay al menos MIN_HISTORIAL).
  * Severidad CRITICA  : temperatura >= 85 C  o  consumo >= 4000 W.
  * Severidad ADVERTENCIA: |z-score| >= 3 (anomalia estadistica).
"""
from statistics import mean, pstdev
from typing import Optional

VENTANA = 10
HISTORIAL = VENTANA - 1
MIN_HISTORIAL = 5

TEMP_MIN, TEMP_MAX = -40.0, 125.0
CONSUMO_MIN, CONSUMO_MAX = 0.0, 10000.0

TEMP_CRITICA = 85.0
CONSUMO_CRITICO = 4000.0
Z_UMBRAL = 3.0
SIGMA_MIN = 0.5  # evita z-scores enormes cuando el sensor es casi constante


def validar_rangos(temperatura: float, consumo_w: float) -> list[str]:
    """Devuelve la lista de errores de rango (vacia si la lectura es valida)."""
    errores = []
    if not TEMP_MIN <= temperatura <= TEMP_MAX:
        errores.append(f"temperatura fuera de rango [{TEMP_MIN}, {TEMP_MAX}]")
    if not CONSUMO_MIN <= consumo_w <= CONSUMO_MAX:
        errores.append(f"consumo_w fuera de rango [{CONSUMO_MIN}, {CONSUMO_MAX}]")
    return errores


def evaluar(temperatura: float, consumo_w: float, previas: list[float]) -> dict:
    """Calcula promedio movil, z-score y alerta.

    `previas` son las temperaturas anteriores del sensor, de la mas reciente a
    la mas antigua (maximo HISTORIAL elementos).
    """
    previas = previas[:HISTORIAL]
    promedio = round(mean(previas + [temperatura]), 2)

    zscore: Optional[float] = None
    if len(previas) >= MIN_HISTORIAL:
        sigma = max(pstdev(previas), SIGMA_MIN)
        zscore = round((temperatura - mean(previas)) / sigma, 2)

    severidad = motivo = valor = None
    if temperatura >= TEMP_CRITICA:
        severidad, motivo, valor = "CRITICA", "temperatura_critica", temperatura
    elif consumo_w >= CONSUMO_CRITICO:
        severidad, motivo, valor = "CRITICA", "consumo_critico", consumo_w
    elif zscore is not None and abs(zscore) >= Z_UMBRAL:
        severidad, motivo, valor = "ADVERTENCIA", "anomalia_zscore", temperatura

    return {"promedio_movil": promedio, "zscore": zscore,
            "severidad": severidad, "motivo": motivo, "valor": valor}
