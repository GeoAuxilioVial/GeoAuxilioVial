"""Acceso a datos de vigencia documental (HU-16)."""
from sqlalchemy.orm import Session

from app.domain.documentos_requeridos_domain import DocumentoRequerido
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import (
	DatosProveedor,
	DocumentoProveedor,
)
from app.domain.proveedor_hu16_domain import AuditoriaDocumento


def obtener_proveedor_por_usuario(db: Session, usuario_id: int) -> Proveedor | None:
	return (
		db.query(Proveedor)
		.filter(Proveedor.usuario_id == usuario_id)
		.first()
	)


def obtener_proveedor(db: Session, proveedor_id: int) -> Proveedor | None:
	return db.get(Proveedor, proveedor_id)


def obtener_perfil(db: Session, proveedor_id: int) -> DatosProveedor | None:
	return db.get(DatosProveedor, proveedor_id)


def listar_proveedores(db: Session) -> list[Proveedor]:
	return (
		db.query(Proveedor)
		.join(DatosProveedor, DatosProveedor.proveedor_id == Proveedor.id)
		.order_by(Proveedor.id)
		.all()
	)


def listar_documentos(
	db: Session, proveedor_id: int
) -> list[DocumentoProveedor]:
	return (
		db.query(DocumentoProveedor)
		.filter(DocumentoProveedor.proveedor_id == proveedor_id)
		.order_by(DocumentoProveedor.id)
		.all()
	)


def listar_requisitos(
	db: Session, tipo_proveedor: str
) -> list[DocumentoRequerido]:
	return (
		db.query(DocumentoRequerido)
		.filter(DocumentoRequerido.tipo_proveedor == tipo_proveedor)
		.order_by(DocumentoRequerido.id)
		.all()
	)


def obtener_auditoria_documento(
	db: Session, documento_id: int, evento: str
) -> AuditoriaDocumento | None:
	return (
		db.query(AuditoriaDocumento)
		.filter(
			AuditoriaDocumento.documento_id == documento_id,
			AuditoriaDocumento.evento == evento,
		)
		.first()
	)


def agregar_auditoria(db: Session, auditoria: AuditoriaDocumento) -> None:
	db.add(auditoria)


def contar_auditorias(
	db: Session, proveedor_id: int, evento: str | None = None
) -> int:
	consulta = db.query(AuditoriaDocumento).filter(
		AuditoriaDocumento.proveedor_id == proveedor_id
	)
	if evento is not None:
		consulta = consulta.filter(AuditoriaDocumento.evento == evento)
	return consulta.count()
