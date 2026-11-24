"""Auditoría de eventos de vigencia documental (HU-16)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditoriaDocumento(Base):
	__tablename__ = "auditoria_documentos_proveedor"
	__table_args__ = (
		UniqueConstraint(
			"documento_id",
			"evento",
			name="uq_auditoria_documento_evento",
		),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	proveedor_id: Mapped[int] = mapped_column(
		ForeignKey("proveedores.id"), nullable=False, index=True
	)
	documento_id: Mapped[int] = mapped_column(
		ForeignKey("documentos_proveedor.id"), nullable=False, index=True
	)
	evento: Mapped[str] = mapped_column(String(40), nullable=False)
	registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	detalle: Mapped[str] = mapped_column(String(500), nullable=False)
