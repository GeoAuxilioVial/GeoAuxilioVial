"""Esquemas de entrada y salida de zonas de cobertura (HU-03)."""
from pydantic import BaseModel, ConfigDict, Field

from app.domain.zonas_cobertura_domain import ZonaCobertura


class ZonaEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid")

	nombre: str = Field(min_length=2, max_length=100)
	latitud_centro: float = Field(alias="latitudCentro", ge=-90, le=90)
	longitud_centro: float = Field(alias="longitudCentro", ge=-180, le=180)
	radio_km: float = Field(alias="radioKm", gt=0)
	activa: bool


def zona_a_dict(zona: ZonaCobertura) -> dict:
	return {
		"zonaId": zona.zona_id,
		"nombre": zona.nombre,
		"latitudCentro": zona.latitud_centro,
		"longitudCentro": zona.longitud_centro,
		"radioKm": zona.radio_km,
		"activa": zona.activa,
	}
