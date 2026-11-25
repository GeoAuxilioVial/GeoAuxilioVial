"""Acceso a datos de las zonas de cobertura (HU-03)."""
from sqlalchemy.orm import Session

from app.domain.proveedor_hu14_domain import ProveedorZonaCobertura
from app.domain.zonas_cobertura_domain import ZonaCobertura


def listar(db: Session, activa: bool | None = None) -> list[ZonaCobertura]:
	consulta = db.query(ZonaCobertura)
	if activa is not None:
		consulta = consulta.filter(ZonaCobertura.activa == activa)
	return consulta.order_by(ZonaCobertura.id).all()


def obtener(db: Session, id_: int) -> ZonaCobertura | None:
	return db.get(ZonaCobertura, id_)


def obtener_por_nombre(db: Session, nombre: str) -> ZonaCobertura | None:
	return db.query(ZonaCobertura).filter(ZonaCobertura.nombre == nombre).first()


def guardar(db: Session, zona: ZonaCobertura) -> ZonaCobertura:
	db.add(zona)
	db.commit()
	db.refresh(zona)
	return zona


def eliminar(db: Session, zona: ZonaCobertura) -> None:
	db.delete(zona)
	db.commit()


def contar_proveedores_asociados(db: Session, id_: int) -> int:
	return (
		db.query(ProveedorZonaCobertura)
		.filter(ProveedorZonaCobertura.zona_id == id_)
		.count()
	)
