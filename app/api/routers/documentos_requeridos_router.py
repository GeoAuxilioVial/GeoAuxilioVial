"""Endpoints de documentos requeridos (HU-03)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.documentos_requeridos_schemas import DocumentosRequeridosEntrada, documentos_a_dict
from app.core.database import get_db
from app.core.errors import ErrorNegocio, sobre
from app.core.security import requiere_admin, requiere_autenticacion
from app.services import documentos_requeridos_service as servicio

router = APIRouter(prefix="/api/v1/parametros/documentos-requeridos", tags=["Documentos requeridos"])


@router.get("")
def consultar_documentos(
	tipoProveedor: str | None = None,
	db: Session = Depends(get_db),
	_: dict = Depends(requiere_autenticacion),
):
	if not tipoProveedor:
		raise ErrorNegocio(
			422,
			"Uno o más campos no cumplen las validaciones",
			{"errores": [{"campo": "tipoProveedor", "codigo": "CAMPO_OBLIGATORIO", "mensaje": "El tipo de proveedor es obligatorio"}]},
		)
	docs = servicio.consultar(db, tipoProveedor)
	return sobre(True, "Documentos requeridos consultados", documentos_a_dict(tipoProveedor, docs))


@router.put("/{tipo_proveedor}")
def actualizar_documentos(
	tipo_proveedor: str,
	datos: DocumentosRequeridosEntrada,
	db: Session = Depends(get_db),
	_: dict = Depends(requiere_admin),
):
	docs = servicio.actualizar(db, tipo_proveedor, datos)
	return sobre(True, "Documentos requeridos actualizados", documentos_a_dict(tipo_proveedor, docs))
