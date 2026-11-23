"""Endpoint privado de ubicación GPS del proveedor."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.ubicacion_schemas import UbicacionEntrada, ubicacion_a_dict
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_autenticacion
from app.services import ubicacion_service as servicio

router = APIRouter(prefix="/api/v1/proveedores", tags=["Proveedores"])


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
