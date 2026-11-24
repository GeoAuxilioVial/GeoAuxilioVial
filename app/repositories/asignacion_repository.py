"""Acceso transaccional a solicitudes, asignaciones y su auditoría (HU-20)."""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.auxilio_domain import (
	AsignacionAuxilio,
	AuditoriaAsignacion,
	SolicitudAuxilio,
)
from app.domain.proveedor_domain import Proveedor


def obtener_proveedor_por_usuario(db: Session, usuario_id: int) -> Proveedor | None:
	return db.scalar(
		select(Proveedor).where(Proveedor.usuario_id == usuario_id)
	)


def obtener_asignacion(db: Session, asignacion_id: int) -> AsignacionAuxilio | None:
	return db.get(AsignacionAuxilio, asignacion_id)


def obtener_solicitud(db: Session, solicitud_id: int) -> SolicitudAuxilio | None:
	return db.get(SolicitudAuxilio, solicitud_id)


def obtener_detalle(db: Session, asignacion_id: int):
	return db.execute(
		select(AsignacionAuxilio, SolicitudAuxilio)
		.join(
			SolicitudAuxilio,
			SolicitudAuxilio.id == AsignacionAuxilio.solicitud_id,
		)
		.where(AsignacionAuxilio.id == asignacion_id)
	).first()


def listar_vencidas(
	db: Session, ahora: datetime
) -> list[tuple[int, int, int, int]]:
	return list(
		db.execute(
			select(
				AsignacionAuxilio.id,
				AsignacionAuxilio.version,
				AsignacionAuxilio.solicitud_id,
				AsignacionAuxilio.proveedor_id,
			).where(
				AsignacionAuxilio.estado == "PENDIENTE",
				AsignacionAuxilio.expira_en <= ahora,
			)
		).all()
	)


def vencer_asignacion(
	db: Session, asignacion_id: int, version: int, ahora: datetime
) -> bool:
	resultado = db.execute(
		update(AsignacionAuxilio)
		.where(
			AsignacionAuxilio.id == asignacion_id,
			AsignacionAuxilio.version == version,
			AsignacionAuxilio.estado == "PENDIENTE",
			AsignacionAuxilio.expira_en <= ahora,
		)
		.values(estado="EXPIRADA", respondida_en=ahora, version=version + 1)
		.execution_options(synchronize_session=False)
	)
	return resultado.rowcount == 1


def actualizar_estado_solicitud(
	db: Session,
	solicitud_id: int,
	version: int,
	estado_anterior: str,
	estado_nuevo: str,
) -> bool:
	resultado = db.execute(
		update(SolicitudAuxilio)
		.where(
			SolicitudAuxilio.id == solicitud_id,
			SolicitudAuxilio.version == version,
			SolicitudAuxilio.estado == estado_anterior,
		)
		.values(estado=estado_nuevo, version=version + 1)
		.execution_options(synchronize_session=False)
	)
	return resultado.rowcount == 1


def responder_asignacion(
	db: Session,
	asignacion_id: int,
	version: int,
	decision: str,
	observacion: str | None,
	ahora: datetime,
) -> bool:
	estado_nuevo = "ACEPTADA" if decision == "ACEPTAR" else "RECHAZADA"
	resultado = db.execute(
		update(AsignacionAuxilio)
		.where(
			AsignacionAuxilio.id == asignacion_id,
			AsignacionAuxilio.version == version,
			AsignacionAuxilio.estado == "PENDIENTE",
			AsignacionAuxilio.expira_en > ahora,
		)
		.values(
			estado=estado_nuevo,
			decision=decision,
			observacion=observacion,
			respondida_en=ahora,
			version=version + 1,
		)
		.execution_options(synchronize_session=False)
	)
	return resultado.rowcount == 1


def proveedores_excluidos(db: Session, solicitud_id: int) -> set[int]:
	return set(
		db.scalars(
			select(AsignacionAuxilio.proveedor_id).where(
				AsignacionAuxilio.solicitud_id == solicitud_id,
				AsignacionAuxilio.estado.in_(("RECHAZADA", "EXPIRADA")),
			)
		).all()
	)


def obtener_asignacion_pendiente(
	db: Session, solicitud_id: int
) -> AsignacionAuxilio | None:
	return db.scalar(
		select(AsignacionAuxilio).where(
			AsignacionAuxilio.solicitud_id == solicitud_id,
			AsignacionAuxilio.estado == "PENDIENTE",
		)
	)


def guardar_auditoria(
	db: Session,
	asignacion_id: int,
	proveedor_id: int,
	evento: str,
	fecha: datetime,
	observacion: str | None = None,
) -> AuditoriaAsignacion:
	auditoria = AuditoriaAsignacion(
		asignacion_id=asignacion_id,
		proveedor_id=proveedor_id,
		evento=evento,
		fecha=fecha,
		observacion=observacion,
	)
	db.add(auditoria)
	return auditoria
