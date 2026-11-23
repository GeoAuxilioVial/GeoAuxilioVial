"""Reglas de negocio de documentos requeridos (HU-03)."""
from sqlalchemy.orm import Session

from app.api.schemas.documentos_requeridos_schemas import DocumentosRequeridosEntrada
from app.core.errors import ErrorNegocio
from app.domain.documentos_requeridos_domain import TIPOS_DOCUMENTO, TIPOS_PROVEEDOR, DocumentoRequerido
from app.repositories import documentos_requeridos_repository as repo


def sembrar_documentos_base(db: Session) -> None:
	"""Siembra una configuración inicial por tipo de proveedor si no existe."""
	for tipo in TIPOS_PROVEEDOR:
		if not repo.listar_por_tipo(db, tipo):
			db.add(DocumentoRequerido(tipo_proveedor=tipo, tipo_documento="IDENTIFICACION", exige_vigencia=True))
			db.add(DocumentoRequerido(tipo_proveedor=tipo, tipo_documento="SOAT", exige_vigencia=True))
	db.commit()


def consultar(db: Session, tipo_proveedor: str) -> list[DocumentoRequerido]:
	if tipo_proveedor not in TIPOS_PROVEEDOR:
		raise ErrorNegocio(
			422,
			"Uno o más campos no cumplen las validaciones",
			{"errores": [{"campo": "tipoProveedor", "codigo": "VALOR_FUERA_DE_CATALOGO", "mensaje": "El tipo de proveedor no pertenece al catálogo"}]},
		)
	return repo.listar_por_tipo(db, tipo_proveedor)


def actualizar(db: Session, tipo_proveedor: str, datos: DocumentosRequeridosEntrada) -> list[DocumentoRequerido]:
	if tipo_proveedor not in TIPOS_PROVEEDOR:
		raise ErrorNegocio(404, "Recurso no encontrado")
	if not datos.documentos_requeridos:
		raise ErrorNegocio(
			422,
			"Uno o más campos no cumplen las validaciones",
			{"errores": [{"campo": "documentosRequeridos", "codigo": "CAMPO_OBLIGATORIO", "mensaje": "La lista no puede estar vacía"}]},
		)
	errores = [
		{"campo": f"documentosRequeridos.{i}.tipoDocumento", "codigo": "VALOR_FUERA_DE_CATALOGO", "mensaje": "El tipo de documento no pertenece al catálogo"}
		for i, d in enumerate(datos.documentos_requeridos)
		if d.tipo_documento not in TIPOS_DOCUMENTO
	]
	if errores:
		raise ErrorNegocio(422, "Uno o más campos no cumplen las validaciones", {"errores": errores})
	nuevos = {
		d.tipo_documento: DocumentoRequerido(
			tipo_proveedor=tipo_proveedor, tipo_documento=d.tipo_documento, exige_vigencia=d.exige_vigencia
		)
		for d in datos.documentos_requeridos
	}
	return repo.reemplazar(db, tipo_proveedor, list(nuevos.values()))
