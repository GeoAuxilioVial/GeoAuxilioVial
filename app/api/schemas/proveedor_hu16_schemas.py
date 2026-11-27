"""Serialización de documentos y estado de vigencia (HU-16)."""
from datetime import date, datetime

from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import DocumentoProveedor


def documento_vigencia_a_dict(documento: DocumentoProveedor) -> dict:
	return {
		"documentoId": documento.documento_id,
		"tipoDocumento": documento.tipo_documento,
		"fechaVencimiento": (
			documento.fecha_vencimiento.isoformat()
			if isinstance(documento.fecha_vencimiento, date)
			else None
		),
		"estado": documento.estado,
		"creadoEn": (
			documento.creado_en.isoformat()
			if isinstance(documento.creado_en, datetime)
			else None
		),
		"revisadoEn": (
			documento.revisado_en.isoformat()
			if isinstance(documento.revisado_en, datetime)
			else None
		),
		"motivo": documento.motivo,
		"reemplazaDocumentoId": (
			f"doc_{documento.reemplaza_documento_id:03d}"
			if documento.reemplaza_documento_id is not None
			else None
		),
	}


def documentos_proveedor_a_dict(
	proveedor: Proveedor,
	documentos: list[DocumentoProveedor],
	incluir_proveedor_id: bool = False,
) -> dict:
	datos = {
		"habilitado": proveedor.estado_habilitacion == "HABILITADO",
		"estadoHabilitacion": proveedor.estado_habilitacion,
		"motivo": proveedor.motivo_habilitacion,
		"documentos": [documento_vigencia_a_dict(doc) for doc in documentos],
	}
	if incluir_proveedor_id:
		datos["proveedorId"] = proveedor.proveedor_id
	return datos
