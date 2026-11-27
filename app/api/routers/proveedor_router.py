"""Endpoint privado de ubicación GPS del proveedor."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.proveedor_hu14_schemas import (
	DocumentoProveedorEntrada,
	RegistroProveedorEntrada,
	RevisionDocumentoEntrada,
	documento_a_dict,
	proveedor_a_dict,
)
from app.api.schemas.ubicacion_schemas import UbicacionEntrada, ubicacion_a_dict
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_autenticacion
from app.services import ubicacion_service as servicio
from app.services import proveedor_hu14_service as servicio_hu14
from app.services import proveedor_hu16_service as servicio_hu16

router = APIRouter(prefix="/api/v1/proveedores", tags=["Proveedores"])
backoffice_router = APIRouter(
	prefix="/api/v1/backoffice/proveedores",
	tags=["Revisión de documentos de proveedores"],
)


@router.post("", status_code=201)
def registrar_proveedor(
	datos: RegistroProveedorEntrada,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	resultado = servicio_hu14.registrar(db, payload, datos)
	return sobre(
		True,
		"Proveedor registrado; pendiente de validación de documentos",
		proveedor_a_dict(
			resultado["proveedor"],
			resultado["perfil"],
			resultado["zonas"],
			resultado["requisitos"],
		),
	)


@router.post("/documentos", status_code=201)
def cargar_documento(
	datos: DocumentoProveedorEntrada,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	documento = servicio_hu14.cargar_documento(db, payload, datos)
	return sobre(True, "Documento recibido para revisión", documento_a_dict(documento))


@router.get("/me/documentos")
def consultar_mis_documentos(
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	datos = servicio_hu16.consultar_mis_documentos(db, payload)
	return sobre(True, "Documentos consultados", datos)


@backoffice_router.patch("/{proveedor_id}/documentos/{documento_id}")
def revisar_documento(
	proveedor_id: str,
	documento_id: str,
	datos: RevisionDocumentoEntrada,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	resultado = servicio_hu14.revisar_documento(
		db, payload, proveedor_id, documento_id, datos
	)
	return sobre(
		True,
		"Decisión registrada",
		{
			"documentoId": resultado["documento"].documento_id,
			"estado": resultado["documento"].estado,
			"estadoHabilitacion": resultado["estado_habilitacion"],
			"proveedorHabilitado": resultado["proveedor_habilitado"],
		},
	)


@backoffice_router.get("/{proveedor_id}/documentos")
def consultar_documentos_proveedor(
	proveedor_id: str,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	datos = servicio_hu16.consultar_documentos_proveedor(
		db, payload, proveedor_id
	)
	return sobre(True, "Documentos del proveedor consultados", datos)


@router.put("/me/ubicacion")
def actualizar_ubicacion(
	datos: UbicacionEntrada,
	payload: dict = Depends(requiere_autenticacion),
	db: Session = Depends(get_db),
):
	proveedor = servicio.actualizar(db, payload, datos)
	return sobre(
		True,
		"Ubicación actualizada",
		ubicacion_a_dict(proveedor),
	)
