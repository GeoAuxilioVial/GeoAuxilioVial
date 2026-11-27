"""Contratos de entrada y serialización de HU-06."""
import re
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


Monto = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class RecargoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepto: str = Field(min_length=2, max_length=60, pattern=r"^[A-Z0-9_]+$")
    valor: Monto


class TarifarioActualizacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moneda: str = Field(min_length=3, max_length=3)
    tarifaBase: Monto
    valorPorKm: Monto
    recargos: list[RecargoEntrada] = Field(default_factory=list, max_length=50)

    @field_validator("moneda")
    @classmethod
    def validar_moneda(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("La moneda debe ser un código ISO de tres letras")
        return value

    @field_validator("recargos")
    @classmethod
    def conceptos_unicos(cls, value):
        conceptos = [item.concepto for item in value]
        if len(conceptos) != len(set(conceptos)):
            raise ValueError("No se permiten conceptos de recargo duplicados")
        return value


class MetodoPagoActualizacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    habilitado: bool


def tarifario_a_dict(tarifario) -> dict:
    return {
        "tarifarioVersion": tarifario.version,
        "moneda": tarifario.moneda,
        "tarifaBase": float(tarifario.tarifa_base),
        "valorPorKm": float(tarifario.valor_por_km),
        "recargos": [
            {"concepto": recargo.concepto, "valor": float(recargo.valor)}
            for recargo in tarifario.recargos
        ],
        "vigente": tarifario.vigente,
    }


def metodo_pago_a_dict(metodo) -> dict:
    return {
        "metodoPagoId": metodo.id,
        "codigo": metodo.codigo,
        "nombre": metodo.nombre,
        "habilitado": metodo.habilitado,
    }
