"""Reglas de consulta y respuesta de asignaciones de auxilio (HU-20)."""
import re
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.asignacion_schemas import (
	RespuestaAsignacionEntrada,
	asignacion_detalle_a_dict,
	respuesta_asignacion_a_dict,
)
from app.core.config import settings
from app.core.errors import ErrorNegocio, ZONA
from app.domain.auxilio_domain import AsignacionAuxilio
from app.repositories import asignacion_repository as repo
from app.services.proveedor_cercano_service import buscar_cercanos

CODIGOS_DECISION = {"ACEPTAR", "RECHAZAR"}


class _SolicitudCambioConcurrencia(Exception):
	pass


def _error_validacion(campo: str, codigo: str, mensaje: str) -> ErrorNegocio:
	return ErrorNegocio(
		422,
		"Uno o más campos no cumplen las validaciones",
		{"errores": [{"campo": campo, "codigo": codigo, "mensaje": mensaje}]},
	)


def _error_conflicto(codigo: str, mensaje: str) -> ErrorNegocio:
	return ErrorNegocio(409, mensaje, {"codigo": codigo})


def _id_numerico(valor: str, prefijo: str) -> int:
	if not re.fullmatch(rf"{prefijo}_[0-9]+", valor):
		raise ErrorNegocio(404, "Recurso no encontrado")
	return int(valor.removeprefix(f"{prefijo}_"))


def _proveedor_autenticado(db: Session, payload: dict):
	roles = payload.get("roles")
	if not isinstance(roles, list):
		rol = payload.get("rol")
		roles = [rol] if isinstance(rol, str) else []
	if "PROVEEDOR" not in roles:
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")

	sub = payload.get("sub")
	if not isinstance(sub, str) or not re.fullmatch(r"usr_[0-9]+", sub):
		raise ErrorNegocio(404, "Recurso no encontrado")
	proveedor = repo.obtener_proveedor_por_usuario(
		db, int(sub.removeprefix("usr_"))
	)
	if proveedor is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	return proveedor


def _fecha_ahora() -> datetime:
	return datetime.now(ZONA)


def _fecha_local(valor: datetime) -> datetime:
	return valor.replace(tzinfo=ZONA) if valor.tzinfo is None else valor


def _es_conflicto_de_asignacion(exc: IntegrityError) -> bool:
	constraint = getattr(exc.orig, "constraint_name", None)
	if constraint in {
		"uq_asignacion_pendiente_solicitud",
		"uq_asignacion_pendiente_proveedor",
	}:
		return True
	mensaje = str(exc.orig).lower()
	return (
		"unique constraint failed" in mensaje
		and (
			"asignaciones_auxilio.solicitud_id" in mensaje
			or "asignaciones_auxilio.proveedor_id" in mensaje
		)
	)


def _verificar_conflicto_respuesta(
	db: Session,
	asignacion_id: int,
	version_esperada: int,
) -> None:
	db.expire_all()
	expirar_asignaciones_vencidas(db)
	db.expire_all()
	asignacion = repo.obtener_asignacion(db, asignacion_id)
	if asignacion is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	if (
		asignacion.estado == "EXPIRADA"
		or _fecha_local(asignacion.expira_en) <= _fecha_ahora()
	):
		raise _error_conflicto(
			"ASIGNACION_EXPIRADA",
			"La asignación expiró antes de recibir respuesta",
		)
	if (
		asignacion.version != version_esperada
		or asignacion.estado != "PENDIENTE"
	):
		raise _error_conflicto(
			"ASIGNACION_YA_RESPONDIDA",
			"La asignación ya fue respondida",
		)


def expirar_asignaciones_vencidas(
	db: Session,
	ahora: datetime | None = None,
) -> int:
	"""Expira asignaciones vencidas una sola vez mediante actualizaciones CAS."""
	ahora = _fecha_local(ahora or _fecha_ahora())
	expiradas = 0
	for asignacion_id, version, solicitud_id, proveedor_id in repo.listar_vencidas(
		db, ahora
	):
		with db.begin_nested():
			if not repo.vencer_asignacion(db, asignacion_id, version, ahora):
				continue
			solicitud = repo.obtener_solicitud(db, solicitud_id)
			if solicitud is None or solicitud.estado != "ASIGNADA":
				raise RuntimeError(
					"La asignación pendiente no tiene una solicitud ASIGNADA"
				)
			if not repo.actualizar_estado_solicitud(
				db,
				solicitud_id,
				solicitud.version,
				"ASIGNADA",
				"BUSCANDO_PROVEEDOR",
			):
				raise RuntimeError(
					"La solicitud cambió durante la expiración de la asignación"
				)
			repo.guardar_auditoria(
				db,
				asignacion_id,
				proveedor_id,
				"EXPIRADA",
				ahora,
			)
			expiradas += 1
	if expiradas:
		db.commit()
	return expiradas


def asignar_proveedor_mas_cercano(
	db: Session,
	solicitud_id: str,
) -> AsignacionAuxilio | None:
	"""Crea atómicamente la asignación pendiente al siguiente candidato elegible."""
	expirar_asignaciones_vencidas(db)
	solicitud_pk = _id_numerico(solicitud_id, "aux")
	solicitud = repo.obtener_solicitud(db, solicitud_pk)
	if solicitud is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	if solicitud.estado != "BUSCANDO_PROVEEDOR":
		existente = repo.obtener_asignacion_pendiente(db, solicitud_pk)
		if existente is not None:
			return existente
		raise _error_conflicto(
			"TRANSICION_INVALIDA",
			"La solicitud no está buscando proveedor",
		)

	existente = repo.obtener_asignacion_pendiente(db, solicitud_pk)
	if existente is not None:
		return existente
	excluidos = repo.proveedores_excluidos(db, solicitud_pk)
	candidatos = buscar_cercanos(
		db,
		{"roles": ["CLIENTE"]},
		solicitud.latitud,
		solicitud.longitud,
		solicitud.tipo_servicio,
		settings.radio_busqueda_max_km,
	)["proveedores"]
	ahora = _fecha_ahora()
	for candidato in candidatos:
		proveedor_id = _id_numerico(candidato["id"], "prov")
		if proveedor_id in excluidos:
			continue
		asignacion = AsignacionAuxilio(
			solicitud_id=solicitud_pk,
			proveedor_id=proveedor_id,
			estado="PENDIENTE",
			creada_en=ahora,
			expira_en=ahora
			+ timedelta(seconds=settings.asignacion_plazo_respuesta_segundos),
			version=1,
		)
		try:
			with db.begin_nested():
				if not repo.actualizar_estado_solicitud(
					db,
					solicitud_pk,
					solicitud.version,
					"BUSCANDO_PROVEEDOR",
					"ASIGNADA",
				):
					raise _SolicitudCambioConcurrencia
				db.add(asignacion)
				db.flush()
				repo.guardar_auditoria(
					db,
					asignacion.id,
					proveedor_id,
					"ASIGNADA",
					ahora,
				)
			db.commit()
			db.refresh(asignacion)
			return asignacion
		except IntegrityError as exc:
			if not _es_conflicto_de_asignacion(exc):
				raise
			db.expire_all()
			solicitud = repo.obtener_solicitud(db, solicitud_pk)
			if solicitud is None or solicitud.estado != "BUSCANDO_PROVEEDOR":
				return repo.obtener_asignacion_pendiente(db, solicitud_pk)
			excluidos.add(proveedor_id)
		except _SolicitudCambioConcurrencia:
			db.expire_all()
			return repo.obtener_asignacion_pendiente(db, solicitud_pk)

	db.expire_all()
	solicitud = repo.obtener_solicitud(db, solicitud_pk)
	if solicitud is None or solicitud.estado != "BUSCANDO_PROVEEDOR":
		return repo.obtener_asignacion_pendiente(db, solicitud_pk)
	if repo.actualizar_estado_solicitud(
		db,
		solicitud_pk,
		solicitud.version,
		"BUSCANDO_PROVEEDOR",
		"SIN_PROVEEDOR",
	):
		db.commit()
	else:
		db.rollback()
	return None


def consultar_asignacion(
	db: Session,
	payload: dict,
	asignacion_id: str,
) -> dict:
	proveedor = _proveedor_autenticado(db, payload)
	expirar_asignaciones_vencidas(db)
	asignacion_pk = _id_numerico(asignacion_id, "asg")
	detalle = repo.obtener_detalle(db, asignacion_pk)
	if detalle is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	asignacion, solicitud = detalle
	if asignacion.proveedor_id != proveedor.id:
		raise ErrorNegocio(404, "Recurso no encontrado")
	return asignacion_detalle_a_dict(asignacion, solicitud)


def responder_asignacion(
	db: Session,
	payload: dict,
	asignacion_id: str,
	datos: RespuestaAsignacionEntrada,
) -> dict:
	proveedor = _proveedor_autenticado(db, payload)
	if datos.decision not in CODIGOS_DECISION:
		raise _error_validacion(
			"decision",
			"VALOR_FUERA_DE_CATALOGO",
			"Los valores permitidos son ACEPTAR y RECHAZAR",
		)

	expirar_asignaciones_vencidas(db)
	asignacion_pk = _id_numerico(asignacion_id, "asg")
	asignacion = repo.obtener_asignacion(db, asignacion_pk)
	if asignacion is None or asignacion.proveedor_id != proveedor.id:
		raise ErrorNegocio(404, "Recurso no encontrado")
	if asignacion.estado == "EXPIRADA":
		raise _error_conflicto(
			"ASIGNACION_EXPIRADA",
			"La asignación expiró antes de recibir respuesta",
		)
	if asignacion.estado != "PENDIENTE":
		raise _error_conflicto(
			"ASIGNACION_YA_RESPONDIDA",
			"La asignación ya fue respondida",
		)
	version_asignacion = asignacion.version

	ahora = _fecha_ahora()
	if _fecha_local(asignacion.expira_en) <= ahora:
		expirar_asignaciones_vencidas(db, ahora)
		raise _error_conflicto(
			"ASIGNACION_EXPIRADA",
			"La asignación expiró antes de recibir respuesta",
		)

	solicitud = repo.obtener_solicitud(db, asignacion.solicitud_id)
	if solicitud is None:
		raise _error_conflicto(
			"TRANSICION_INVALIDA",
			"La solicitud no está asignada",
		)
	if solicitud.estado != "ASIGNADA":
		_verificar_conflicto_respuesta(
			db, asignacion_pk, version_asignacion
		)
		raise _error_conflicto(
			"TRANSICION_INVALIDA",
			"La solicitud no está asignada",
		)
	if not repo.responder_asignacion(
		db,
		asignacion.id,
		version_asignacion,
		datos.decision,
		datos.observacion,
		ahora,
	):
		db.rollback()
		_verificar_conflicto_respuesta(
			db, asignacion_pk, version_asignacion
		)
		raise _error_conflicto(
			"ASIGNACION_YA_RESPONDIDA",
			"La asignación ya fue respondida",
		)

	estado_solicitud = (
		"ACEPTADA" if datos.decision == "ACEPTAR" else "BUSCANDO_PROVEEDOR"
	)
	if not repo.actualizar_estado_solicitud(
		db,
		solicitud.id,
		solicitud.version,
		"ASIGNADA",
		estado_solicitud,
	):
		db.rollback()
		_verificar_conflicto_respuesta(
			db, asignacion_pk, version_asignacion
		)
		raise _error_conflicto(
			"ASIGNACION_YA_RESPONDIDA",
			"La asignación ya fue respondida",
		)
	repo.guardar_auditoria(
		db,
		asignacion.id,
		proveedor.id,
		f"RESPUESTA_{datos.decision}",
		ahora,
		datos.observacion,
	)
	db.commit()
	return respuesta_asignacion_a_dict(
		asignacion, datos.decision, estado_solicitud
	)
