"""Endpoints de registro e inicio de sesion."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.usuario_schemas import (
	LoginEntrada,
	PerfilActualizacion,
	RegistroEntrada,
	perfil_a_dict,
	usuario_a_dict,
)
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_autenticacion
from app.services import usuario_service as servicio

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticacion"])
perfil_router = APIRouter(prefix="/api/v1/perfil", tags=["Perfil"])


@router.post("/registro", status_code=201)
def registrar(datos: RegistroEntrada, db: Session = Depends(get_db)):
	usuario = servicio.registrar(db, datos)
	return sobre(
		True,
		"Usuario registrado correctamente",
		{"usuario": usuario_a_dict(usuario)},
	)


@router.post("/login")
def iniciar_sesion(datos: LoginEntrada, db: Session = Depends(get_db)):
	resultado = servicio.iniciar_sesion(db, datos)
	return sobre(
		True,
		"Autenticación correcta",
		{
			"usuario": usuario_a_dict(resultado["usuario"]),
			"token": resultado["token"],
			"tipoToken": resultado["tipoToken"],
			"expiraEn": resultado["expiraEn"],
		},
	)


@perfil_router.get("")
def consultar_perfil(
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	usuario = servicio.obtener_perfil(db, payload)
	return sobre(True, "Perfil consultado correctamente", perfil_a_dict(usuario))


@perfil_router.put("")
def actualizar_perfil(
	datos: PerfilActualizacion,
	db: Session = Depends(get_db),
	payload: dict = Depends(requiere_autenticacion),
):
	usuario = servicio.actualizar_perfil(db, payload, datos)
	return sobre(True, "Perfil actualizado correctamente", perfil_a_dict(usuario))
