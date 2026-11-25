"""Entidades de dominio para la parametrización financiera (HU-06)."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RecargoTarifario:
    concepto: str
    valor: Decimal


@dataclass(frozen=True)
class Tarifario:
    id: str
    version: str
    moneda: str
    tarifa_base: Decimal
    valor_por_km: Decimal
    recargos: list[RecargoTarifario]
    vigente: bool


@dataclass(frozen=True)
class MetodoPago:
    id: str
    codigo: str
    nombre: str
    habilitado: bool
