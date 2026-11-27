"""Esquemas de entrada y salida de proveedores y sus documentos (HU-14)."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.domain.documentos_requeridos_domain import DocumentoRequerido
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import DatosProveedor, DocumentoProveedor


class RegistroProveedorEntrada(BaseModel):
	model_config = ConfigDict(
		extra="forbid",
		populate_by_name=True,
		str_strip_whitespace=True,
	)

	nombre_comercial: str = Field(
		alias="nombreComercial", min_length=2, max_length=150
	)
	tipo_proveedor: str = Field(alias="tipoProveedor", min_length=2, max_length=50)
	zonas_cobertura: list[str] = Field(alias="zonasCobertura", min_length=1)


class DocumentoProveedorEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid", populate_by_name=True)

	tipo_documento: str = Field(alias="tipoDocumento", min_length=2, max_length=50)
	archivo_id: str = Field(alias="archivoId", min_length=1, max_length=64)
	fecha_vencimiento: date | None = Field(
		default=None, alias="fechaVencimiento"
	)
	reemplaza_documento_id: str | None = Field(
		default=None, alias="reemplazaDocumentoId", max_length=32
	)


class RevisionDocumentoEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid", populate_by_name=True)

	decision: str = Field(min_length=2, max_length=30)
	motivo: str | None = Field(default=None, max_length=500)


def proveedor_a_dict(
	proveedor: Proveedor,
	datos: DatosProveedor,
	zonas: list[str],
	requisitos: list[DocumentoRequerido],
) -> dict:
	return {
		"proveedorId": proveedor.proveedor_id,
		"nombreComercial": datos.nombre_comercial,
		"tipoProveedor": datos.tipo_proveedor,
		"estadoHabilitacion": proveedor.estado_habilitacion,
		"zonasCobertura": zonas,
		"documentosRequeridos": [
			{
				"tipoDocumento": requisito.tipo_documento,
				"exigeVigencia": requisito.exige_vigencia,
			}
			for requisito in requisitos
		],
	}


def documento_a_dict(documento: DocumentoProveedor) -> dict:
	return {
		"documentoId": documento.documento_id,
		"tipoDocumento": documento.tipo_documento,
		"fechaVencimiento": (
			documento.fecha_vencimiento.isoformat()
			if isinstance(documento.fecha_vencimiento, date)
			else None
		),
		"estado": documento.estado,
	}
