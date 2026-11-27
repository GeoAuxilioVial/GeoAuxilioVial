"""Modelos de perfil, cobertura, archivos y documentos del proveedor (HU-14)."""
from datetime import date, datetime

from sqlalchemy import (
	Boolean,
	Date,
	DateTime,
	ForeignKey,
	Integer,
	String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatosProveedor(Base):
	__tablename__ = "datos_proveedor"

	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), primary_key=True
	)
	nombre_comercial: Mapped[str] = mapped_column(String(150), nullable=False)
	tipo_proveedor: Mapped[str] = mapped_column(String(50), nullable=False)


class ProveedorZonaCobertura(Base):
	__tablename__ = "proveedor_zonas_cobertura"

	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), primary_key=True
	)
	zona_id: Mapped[int] = mapped_column(
		ForeignKey("zonas_cobertura.id"), primary_key=True
	)


class ArchivoPrivado(Base):
	__tablename__ = "archivos_privados"

	archivo_id: Mapped[str] = mapped_column(String(64), primary_key=True)
	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), nullable=False, index=True
	)
	clave_almacenamiento: Mapped[str] = mapped_column(String(512), nullable=False)
	valido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DocumentoProveedor(Base):
	__tablename__ = "documentos_proveedor"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), nullable=False, index=True
	)
	archivo_id: Mapped[str] = mapped_column(
		ForeignKey("archivos_privados.archivo_id"), nullable=False
	)
	tipo_documento: Mapped[str] = mapped_column(String(50), nullable=False)
	fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
	estado: Mapped[str] = mapped_column(
		String(30), nullable=False, default="PENDIENTE_REVISION"
	)
	creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	revisor_usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
	revisado_en: Mapped[datetime | None] = mapped_column(
		DateTime(timezone=True), nullable=True
	)
	motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
	reemplaza_documento_id: Mapped[int | None] = mapped_column(
		ForeignKey("documentos_proveedor.id"), nullable=True
	)

	@property
	def documento_id(self) -> str:
		return f"doc_{self.id:03d}"
