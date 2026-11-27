"""Contratos JSON de asignaciones de auxilio (HU-20)."""
from datetime import datetime

from pydantic import BaseModel

from app.core.errors import ZONA
from app.domain.auxilio_domain import AsignacionAuxilio, SolicitudAuxilio


class RespuestaAsignacionEntrada(BaseModel):
	decision: str
	observacion: str | None = None


def _fecha_iso(valor: datetime) -> str:
	if valor.tzinfo is None:
		valor = valor.replace(tzinfo=ZONA)
	return valor.isoformat(timespec="seconds")


def asignacion_detalle_a_dict(
	asignacion: AsignacionAuxilio,
	solicitud: SolicitudAuxilio,
) -> dict:
	return {
		"asignacionId": asignacion.asignacion_id,
		"estadoAsignacion": asignacion.estado,
		"tipoServicio": solicitud.tipo_servicio,
		"latitud": solicitud.latitud,
		"longitud": solicitud.longitud,
		"expiraEn": _fecha_iso(asignacion.expira_en),
	}


def respuesta_asignacion_a_dict(
	asignacion: AsignacionAuxilio,
	decision: str,
	estado_solicitud: str,
) -> dict:
	return {
		"asignacionId": asignacion.asignacion_id,
		"decision": decision,
		"estadoAsignacion": (
			"ACEPTADA" if decision == "ACEPTAR" else "RECHAZADA"
		),
		"estadoSolicitud": estado_solicitud,
	}
