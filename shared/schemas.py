"""Contrato compartido de la API (Pydantic v2).

La API valida el FORMATO (tipos, sensor_id, fecha con zona horaria).
El procesador valida los RANGOS fisicos (ver shared/analitica.py).
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class LecturaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sensor_id: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$",
                           description="Identificador del dispositivo")
    ts: AwareDatetime = Field(description="Instante de la medicion (ISO 8601 con zona horaria)")
    temperatura: float = Field(allow_inf_nan=False, description="Grados Celsius")
    consumo_w: float = Field(allow_inf_nan=False, description="Consumo electrico en watts")


class AlertaSalida(BaseModel):
    severidad: Literal["CRITICA", "ADVERTENCIA"]
    motivo: str
    valor: float


class LecturaSalida(BaseModel):
    sensor_id: str
    ts: datetime
    temperatura: float
    consumo_w: float
    promedio_movil: float
    zscore: Optional[float] = None
    alerta: Optional[AlertaSalida] = None


class AlertaItem(BaseModel):
    sensor_id: str
    ts: datetime
    severidad: str
    motivo: str
    valor: float
    creada_en: datetime


class Estadisticas(BaseModel):
    total_lecturas: int
    sensores: int
    alertas_criticas: int
    alertas_advertencia: int
