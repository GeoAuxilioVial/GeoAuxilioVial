"""Acceso a datos de perfiles y documentos de proveedor (HU-14)."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.documentos_requeridos_domain import DocumentoRequerido
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import (
	ArchivoPrivado,
	DatosProveedor,
	DocumentoProveedor,
	ProveedorZonaCobertura,
)
from app.domain.usuario_domain import Usuario
from app.domain.zonas_cobertura_domain import ZonaCobertura


def obtener_usuario(db: Session, usuario_id: int) -> Usuario | None:
	return db.get(Usuario, usuario_id)


def obtener_proveedor_por_usuario(db: Session, usuario_id: int) -> Proveedor | None:
	return (
		db.query(Proveedor)
		.filter(Proveedor.usuario_id == usuario_id)
		.first()
	)


def obtener_proveedor(db: Session, proveedor_id: int) -> Proveedor | None:
	return db.get(Proveedor, proveedor_id)


def obtener_datos_proveedor(
	db: Session, proveedor_id: int
) -> DatosProveedor | None:
	return db.get(DatosProveedor, proveedor_id)


def contar_perfiles_proveedor(db: Session, usuario_id: int) -> int:
	return (
		db.query(func.count(Proveedor.id))
		.filter(Proveedor.usuario_id == usuario_id)
		.scalar()
		or 0
	)


def obtener_zona(db: Session, zona_id: int) -> ZonaCobertura | None:
	return db.get(ZonaCobertura, zona_id)


def agregar_proveedor(db: Session, proveedor: Proveedor) -> None:
	db.add(proveedor)
	db.flush()


def agregar_datos_proveedor(db: Session, datos: DatosProveedor) -> None:
	db.add(datos)


def agregar_zona_proveedor(db: Session, asociacion: ProveedorZonaCobertura) -> None:
	db.add(asociacion)


def agregar_documento(db: Session, documento: DocumentoProveedor) -> None:
	db.add(documento)
	db.commit()
	db.refresh(documento)


def obtener_archivo(db: Session, archivo_id: str) -> ArchivoPrivado | None:
	return db.get(ArchivoPrivado, archivo_id)


def registrar_archivo_privado(db: Session, archivo: ArchivoPrivado) -> None:
	db.add(archivo)
	db.commit()


def obtener_documento(db: Session, documento_id: int) -> DocumentoProveedor | None:
	return db.get(DocumentoProveedor, documento_id)


def obtener_documentos(
	db: Session, proveedor_id: int, tipo_documento: str | None = None
) -> list[DocumentoProveedor]:
	consulta = db.query(DocumentoProveedor).filter(
		DocumentoProveedor.proveedor_id == proveedor_id
	)
	if tipo_documento is not None:
		consulta = consulta.filter(
			DocumentoProveedor.tipo_documento == tipo_documento
		)
	return consulta.order_by(DocumentoProveedor.id).all()


def obtener_requisitos(
	db: Session, tipo_proveedor: str
) -> list[DocumentoRequerido]:
	return (
		db.query(DocumentoRequerido)
		.filter(DocumentoRequerido.tipo_proveedor == tipo_proveedor)
		.order_by(DocumentoRequerido.id)
		.all()
	)


def obtener_zonas_proveedor(db: Session, proveedor_id: int) -> list[int]:
	return [
		zona_id
		for (zona_id,) in db.query(ProveedorZonaCobertura.zona_id)
		.filter(ProveedorZonaCobertura.proveedor_id == proveedor_id)
		.order_by(ProveedorZonaCobertura.zona_id)
		.all()
	]
