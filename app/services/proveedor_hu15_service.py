"""Reglas de cambio de disponibilidad operativa (HU-15)."""
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.schemas.proveedor_hu15_schemas import DisponibilidadEntrada
from app.core.errors import ErrorNegocio, ZONA
from app.domain.proveedor_domain import Proveedor
from app.repositories import proveedor_hu15_repository as repo


def _error_validacion(campo: str, codigo: str, mensaje: str) -> ErrorNegocio:
	return ErrorNegocio(
		422,
		"Uno o más campos no cumplen las validaciones",
		{"errores": [{"campo": campo, "codigo": codigo, "mensaje": mensaje}]},
	)


def _roles(payload: dict) -> list[str]:
	roles = payload.get("roles")
	if isinstance(roles, list):
		return [rol for rol in roles if isinstance(rol, str)]
	rol = payload.get("rol")
	return [rol] if isinstance(rol, str) else []


def _usuario_id(payload: dict) -> int:
	sub = payload.get("sub")
	if not isinstance(sub, str) or not re.fullmatch(r"usr_[0-9]+", sub):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")
	return int(sub.removeprefix("usr_"))


def actualizar_disponibilidad(
	db: Session,
	payload: dict,
	datos: DisponibilidadEntrada,
) -> tuple[Proveedor, datetime]:
	if "PROVEEDOR" not in _roles(payload):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")

	if datos.estado not in {"DISPONIBLE", "NO_DISPONIBLE"}:
		raise _error_validacion(
			"estado",
			"VALOR_FUERA_DE_CATALOGO",
			"Los valores permitidos son DISPONIBLE y NO_DISPONIBLE",
		)

	proveedor = repo.obtener_por_usuario(db, _usuario_id(payload))
	if proveedor is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	if (
		datos.estado == "DISPONIBLE"
		and proveedor.estado_habilitacion != "HABILITADO"
	):
		raise ErrorNegocio(
			409,
			"El proveedor no está habilitado: tiene documentos obligatorios pendientes, rechazados o vencidos",
			{"codigo": "PROVEEDOR_NO_HABILITADO"},
		)

	actualizado_en = datetime.now(ZONA)
	proveedor.estado_operativo = datos.estado
	proveedor.estado_operativo_actualizado_en = actualizado_en
	proveedor = repo.guardar(db, proveedor)
	return proveedor, actualizado_en
