"""Reglas de negocio para actualizar la ubicación del proveedor."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.schemas.ubicacion_schemas import UbicacionEntrada
from app.core.errors import ErrorNegocio, ZONA
from app.domain.proveedor_domain import Proveedor
from app.repositories import proveedor_repository as repo


def _usuario_id_desde_token(payload: dict) -> int:
	sub = payload.get("sub")
	if not isinstance(sub, str) or not sub.startswith("usr_"):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")
	try:
		return int(sub.removeprefix("usr_"))
	except ValueError:
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")


def actualizar(db: Session, payload: dict, datos: UbicacionEntrada) -> Proveedor:
	roles = payload.get("roles")
	if not isinstance(roles, list):
		rol_unico = payload.get("rol")
		roles = [rol_unico] if rol_unico else []
	if "PROVEEDOR" not in roles:
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")

	usuario_id = _usuario_id_desde_token(payload)
	proveedor = repo.obtener_por_usuario(db, usuario_id)
	if proveedor is None or proveedor.estado_habilitacion != "HABILITADO":
		raise ErrorNegocio(
			409,
			"El proveedor no está habilitado para operar",
			{"codigo": "PROVEEDOR_NO_HABILITADO"},
		)

	ahora = datetime.now(ZONA)
	proveedor.latitud = datos.latitud
	proveedor.longitud = datos.longitud
	proveedor.precision_metros = datos.precisionMetros
	proveedor.actualizada_en = ahora
	return repo.guardar(db, proveedor)
