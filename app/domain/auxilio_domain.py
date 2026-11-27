"""Modelos de solicitudes y asignaciones de auxilio (HU-20)."""
from datetime import datetime

from sqlalchemy import (
	DateTime,
	Float,
	ForeignKey,
	Index,
	Integer,
	String,
	text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SolicitudAuxilio(Base):
	__tablename__ = "solicitudes_auxilio"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	cliente_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
	tipo_servicio: Mapped[str] = mapped_column(String(50), nullable=False)
	latitud: Mapped[float] = mapped_column(Float, nullable=False)
	longitud: Mapped[float] = mapped_column(Float, nullable=False)
	estado: Mapped[str] = mapped_column(
		String(30), nullable=False, default="BUSCANDO_PROVEEDOR"
	)
	version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

	@property
	def solicitud_id(self) -> str:
		return f"aux_{self.id:03d}"


class AsignacionAuxilio(Base):
	__tablename__ = "asignaciones_auxilio"
	__table_args__ = (
		Index(
			"uq_asignacion_pendiente_solicitud",
			"solicitud_id",
			unique=True,
			sqlite_where=text("estado = 'PENDIENTE'"),
			postgresql_where=text("estado = 'PENDIENTE'"),
		),
		Index(
			"uq_asignacion_pendiente_proveedor",
			"proveedor_id",
			unique=True,
			sqlite_where=text("estado = 'PENDIENTE'"),
			postgresql_where=text("estado = 'PENDIENTE'"),
		),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	solicitud_id: Mapped[int] = mapped_column(
		ForeignKey("solicitudes_auxilio.id"), nullable=False, index=True
	)
	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), nullable=False, index=True
	)
	estado: Mapped[str] = mapped_column(
		String(30), nullable=False, default="PENDIENTE"
	)
	decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
	observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
	creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	respondida_en: Mapped[datetime | None] = mapped_column(
		DateTime(timezone=True), nullable=True
	)
	version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

	@property
	def asignacion_id(self) -> str:
		return f"asg_{self.id:03d}"


class AuditoriaAsignacion(Base):
	__tablename__ = "auditoria_asignaciones"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	asignacion_id: Mapped[int] = mapped_column(
		ForeignKey("asignaciones_auxilio.id"), nullable=False, index=True
	)
	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), nullable=False, index=True
	)
	evento: Mapped[str] = mapped_column(String(30), nullable=False)
	fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
