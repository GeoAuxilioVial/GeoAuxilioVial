"""Acceso a datos de proveedores para HU-17."""
from sqlalchemy.orm import Session

from app.domain.proveedor_domain import Proveedor


def obtener_por_usuario(db: Session, usuario_id: int) -> Proveedor | None:
	return db.query(Proveedor).filter(Proveedor.usuario_id == usuario_id).first()


def guardar(db: Session, proveedor: Proveedor) -> Proveedor:
	db.add(proveedor)
	db.commit()
	db.refresh(proveedor)
	return proveedor
