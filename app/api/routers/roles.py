"""Endpoints del catálogo de roles (HU-01)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.rol import RolEntrada, rol_a_dict
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_admin, requiere_autenticacion
from app.services import rol_service as servicio

router = APIRouter(prefix="/api/v1/parametros/roles", tags=["Roles"])


@router.get("")
def listar_roles(db: Session = Depends(get_db), _: dict = Depends(requiere_autenticacion)):
	roles = [rol_a_dict(r) for r in servicio.listar(db)]
	return sobre(True, "Catálogo de roles", roles)


@router.post("", status_code=201)
def crear_rol(datos: RolEntrada, db: Session = Depends(get_db), _: dict = Depends(requiere_admin)):
	return sobre(True, "Rol registrado", rol_a_dict(servicio.crear(db, datos)))


@router.put("/{rol_id}")
def actualizar_rol(rol_id: str, datos: RolEntrada, db: Session = Depends(get_db), _: dict = Depends(requiere_admin)):
	return sobre(True, "Rol actualizado", rol_a_dict(servicio.actualizar(db, rol_id, datos)))


@router.delete("/{rol_id}")
def eliminar_rol(rol_id: str, db: Session = Depends(get_db), _: dict = Depends(requiere_admin)):
	servicio.eliminar(db, rol_id)
	return sobre(True, "Rol eliminado", None)
