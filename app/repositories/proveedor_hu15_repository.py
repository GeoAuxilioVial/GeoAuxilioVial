"""Acceso a persistencia de disponibilidad del proveedor (HU-15)."""
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.proveedor_domain import Proveedor


def obtener_por_usuario(db: Session, usuario_id: int) -> Proveedor | None:
	return (
		db.query(Proveedor)
		.filter(Proveedor.usuario_id == usuario_id)
		.first()
	)


def guardar(db: Session, proveedor: Proveedor) -> Proveedor:
	db.add(proveedor)
	try:
		db.commit()
	except SQLAlchemyError:
		db.rollback()
		raise
	db.refresh(proveedor)
	return proveedor
