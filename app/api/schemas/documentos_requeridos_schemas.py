"""Esquemas de documentos requeridos (HU-03)."""
from pydantic import BaseModel, ConfigDict, Field

from app.domain.documentos_requeridos_domain import DocumentoRequerido


class DocumentoRequeridoEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid", populate_by_name=True)

	tipo_documento: str = Field(alias="tipoDocumento", min_length=2, max_length=50)
	exige_vigencia: bool = Field(alias="exigeVigencia")


class DocumentosRequeridosEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid", populate_by_name=True)

	documentos_requeridos: list[DocumentoRequeridoEntrada] = Field(alias="documentosRequeridos")


def documentos_a_dict(tipo_proveedor: str, documentos: list[DocumentoRequerido]) -> dict:
	return {
		"tipoProveedor": tipo_proveedor,
		"documentosRequeridos": [
			{"tipoDocumento": d.tipo_documento, "exigeVigencia": d.exige_vigencia} for d in documentos
		],
	}
