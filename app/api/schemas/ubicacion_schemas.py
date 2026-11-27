"""Esquemas de entrada y salida de ubicación GPS."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.proveedor_domain import Proveedor


class UbicacionEntrada(BaseModel):
	model_config = ConfigDict(extra="ignore")

	latitud: float = Field(ge=-90, le=90)
	longitud: float = Field(ge=-180, le=180)
	precisionMetros: float | None = Field(default=None, ge=0)


def ubicacion_a_dict(proveedor: Proveedor) -> dict:
	return {
		"proveedorId": proveedor.proveedor_id,
		"latitud": proveedor.latitud,
		"longitud": proveedor.longitud,
		"precisionMetros": proveedor.precision_metros,
		"actualizadaEn": _fecha_iso(proveedor.actualizada_en),
	}


def _fecha_iso(fecha: datetime | None) -> str | None:
	if fecha is None:
		return None
	from app.core.errors import ZONA

	if fecha.tzinfo is None:
		fecha = fecha.replace(tzinfo=ZONA)
	return fecha.isoformat(timespec="seconds")
