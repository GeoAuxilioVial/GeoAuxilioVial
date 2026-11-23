"""Endpoints de zonas de cobertura (HU-03)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.zonas_cobertura_schemas import ZonaEntrada, zona_a_dict
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_admin, requiere_autenticacion
from app.services import zonas_cobertura_service as servicio

router = APIRouter(prefix="/api/v1/parametros/zonas-cobertura", tags=["Zonas de cobertura"])


@router.get("")
def listar_zonas(
	activa: bool | None = None,
	db: Session = Depends(get_db),
	_: dict = Depends(requiere_autenticacion),
):
	zonas = [zona_a_dict(z) for z in servicio.listar(db, activa)]
	return sobre(True, "Zonas de cobertura consultadas", {"zonas": zonas})


@router.get("/{zona_id}")
def consultar_zona(zona_id: str, db: Session = Depends(get_db), _: dict = Depends(requiere_autenticacion)):
	return sobre(True, "Zona de cobertura consultada", zona_a_dict(servicio.obtener(db, zona_id)))


@router.post("", status_code=201)
def crear_zona(datos: ZonaEntrada, db: Session = Depends(get_db), _: dict = Depends(requiere_admin)):
	return sobre(True, "Zona de cobertura registrada", zona_a_dict(servicio.crear(db, datos)))


@router.put("/{zona_id}")
def actualizar_zona(zona_id: str, datos: ZonaEntrada, db: Session = Depends(get_db), _: dict = Depends(requiere_admin)):
	return sobre(True, "Zona de cobertura actualizada", zona_a_dict(servicio.actualizar(db, zona_id, datos)))


@router.delete("/{zona_id}")
def eliminar_zona(zona_id: str, db: Session = Depends(get_db), _: dict = Depends(requiere_admin)):
	identificador = servicio.eliminar(db, zona_id)
	return sobre(True, "Zona de cobertura eliminada", {"zonaId": identificador})
