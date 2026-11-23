"""Entidad y reglas de las zonas de cobertura (HU-03)."""
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

RADIO_TIERRA_KM = 6371.0


class ZonaCobertura(Base):
	__tablename__ = "zonas_cobertura"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
	latitud_centro: Mapped[float] = mapped_column(Float, nullable=False)
	longitud_centro: Mapped[float] = mapped_column(Float, nullable=False)
	radio_km: Mapped[float] = mapped_column(Float, nullable=False)
	activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

	@property
	def zona_id(self) -> str:
		"""Identificador público: zon_01, zon_02..."""
		return f"zon_{self.id:02d}"

	def cubre_punto(self, latitud: float, longitud: float) -> bool:
		"""Regla de cobertura: el punto está dentro de radio_km del centro y la zona está activa."""
		if not self.activa:
			return False
		return distancia_km(self.latitud_centro, self.longitud_centro, latitud, longitud) <= self.radio_km


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	"""Distancia entre dos puntos por la fórmula de Haversine."""
	d_lat = radians(lat2 - lat1)
	d_lon = radians(lon2 - lon1)
	a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
	return 2 * RADIO_TIERRA_KM * asin(sqrt(a))
