"""Acceso a datos de documentos requeridos (HU-03)."""
from sqlalchemy.orm import Session

from app.domain.documentos_requeridos_domain import DocumentoRequerido


def listar_por_tipo(db: Session, tipo_proveedor: str) -> list[DocumentoRequerido]:
	return (
		db.query(DocumentoRequerido)
		.filter(DocumentoRequerido.tipo_proveedor == tipo_proveedor)
		.order_by(DocumentoRequerido.id)
		.all()
	)


def reemplazar(db: Session, tipo_proveedor: str, nuevos: list[DocumentoRequerido]) -> list[DocumentoRequerido]:
	db.query(DocumentoRequerido).filter(DocumentoRequerido.tipo_proveedor == tipo_proveedor).delete()
	db.add_all(nuevos)
	db.commit()
	return listar_por_tipo(db, tipo_proveedor)
