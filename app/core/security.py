"""Validación de JWT y control de rol Administrador."""
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import ErrorNegocio

bearer = HTTPBearer(auto_error=False)


def requiere_autenticacion(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
	if cred is None or not settings.secret_key:
		raise ErrorNegocio(401, "Autenticación requerida o token inválido")
	try:
		return jwt.decode(cred.credentials, settings.secret_key, algorithms=["HS256"])
	except jwt.PyJWTError:
		raise ErrorNegocio(401, "Autenticación requerida o token inválido")


def requiere_admin(payload: dict = Depends(requiere_autenticacion)) -> dict:
	if payload.get("rol") != "ADMINISTRADOR":
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")
	return payload
