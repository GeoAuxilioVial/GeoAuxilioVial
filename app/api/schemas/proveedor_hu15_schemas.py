"""Esquemas de disponibilidad operativa del proveedor (HU-15)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.errors import ZONA
from app.domain.proveedor_domain import Proveedor


class DisponibilidadEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid")

	estado: str


def disponibilidad_a_dict(
	proveedor: Proveedor, actualizado_en: datetime
) -> dict:
	if actualizado_en.tzinfo is None:
		actualizado_en = actualizado_en.replace(tzinfo=ZONA)
	return {
		"proveedorId": proveedor.proveedor_id,
		"estado": proveedor.estado_operativo,
		"actualizadoEn": actualizado_en.isoformat(timespec="seconds"),
	}
