"""Endpoints de consulta y respuesta de asignaciones de auxilio (HU-20)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.asignacion_schemas import RespuestaAsignacionEntrada
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_autenticacion
from app.services import asignacion_service

router = APIRouter(prefix="/api/v1/auxilio", tags=["Asignaciones de auxilio"])


@router.get("/asignaciones/{asignacion_id}")
def consultar_asignacion(
	asignacion_id: str,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	datos = asignacion_service.consultar_asignacion(
		db, payload, asignacion_id
	)
	return sobre(True, "Asignación consultada", datos)


@router.post("/asignaciones/{asignacion_id}/respuesta")
def responder_asignacion(
	asignacion_id: str,
	datos: RespuestaAsignacionEntrada,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	resultado = asignacion_service.responder_asignacion(
		db, payload, asignacion_id, datos
	)
	return sobre(True, "Respuesta de asignación registrada", resultado)
