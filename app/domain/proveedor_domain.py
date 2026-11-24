"""Modelo mínimo de proveedor requerido por la ubicación operativa."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Proveedor(Base):
	__tablename__ = "proveedores"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	usuario_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
	estado_habilitacion: Mapped[str] = mapped_column(String(30), default="PENDIENTE")
	motivo_habilitacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
	estado_operativo: Mapped[str] = mapped_column(
		String(30),
		nullable=False,
		default="NO_DISPONIBLE",
		server_default="NO_DISPONIBLE",
	)
	latitud: Mapped[float | None] = mapped_column(Float, nullable=True)
	longitud: Mapped[float | None] = mapped_column(Float, nullable=True)
	precision_metros: Mapped[float | None] = mapped_column(Float, nullable=True)
	actualizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

	@property
	def proveedor_id(self) -> str:
		return f"prov_{self.id:03d}"
