"""Entidad de documentos requeridos por tipo de proveedor (HU-03)."""
from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TIPOS_PROVEEDOR = ("GRUA", "MECANICO")
TIPOS_DOCUMENTO = ("IDENTIFICACION", "SOAT", "LICENCIA_CONDUCCION")


class DocumentoRequerido(Base):
	__tablename__ = "documentos_requeridos"
	__table_args__ = (UniqueConstraint("tipo_proveedor", "tipo_documento"),)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	tipo_proveedor: Mapped[str] = mapped_column(String(50), nullable=False)
	tipo_documento: Mapped[str] = mapped_column(String(50), nullable=False)
	exige_vigencia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
