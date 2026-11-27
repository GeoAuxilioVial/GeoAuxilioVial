"""Reglas de consulta y vigencia documental (HU-16)."""
import re
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.api.schemas.proveedor_hu16_schemas import documentos_proveedor_a_dict
from app.core.database import SessionLocal
from app.core.errors import ErrorNegocio, ZONA
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu16_domain import AuditoriaDocumento
from app.repositories import proveedor_hu16_repository as repo

EVENTO_DOCUMENTO_VENCIDO = "DOCUMENTO_VENCIDO"


def _roles(payload: dict) -> list[str]:
	roles = payload.get("roles")
	if isinstance(roles, list):
		return [rol for rol in roles if isinstance(rol, str)]
	rol = payload.get("rol")
	return [rol] if isinstance(rol, str) else []


def _usuario_id(payload: dict) -> int:
	sub = payload.get("sub")
	if not isinstance(sub, str) or not re.fullmatch(r"usr_[0-9]+", sub):
		raise ErrorNegocio(401, "Autenticación requerida o token inválido")
	return int(sub.removeprefix("usr_"))


def _proveedor_o_404(db: Session, proveedor_id: int) -> Proveedor:
	proveedor = repo.obtener_proveedor(db, proveedor_id)
	if proveedor is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	return proveedor


def consultar_mis_documentos(db: Session, payload: dict) -> dict:
	if "PROVEEDOR" not in _roles(payload):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")
	proveedor = repo.obtener_proveedor_por_usuario(db, _usuario_id(payload))
	if proveedor is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	return documentos_proveedor_a_dict(
		proveedor, repo.listar_documentos(db, proveedor.id)
	)


def consultar_documentos_proveedor(
	db: Session, payload: dict, proveedor_publico_id: str
) -> dict:
	if not set(_roles(payload)).intersection({"REVISOR", "ADMINISTRADOR"}):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")
	if not re.fullmatch(r"prov_[0-9]+", proveedor_publico_id):
		raise ErrorNegocio(404, "Recurso no encontrado")
	proveedor_id = int(proveedor_publico_id.removeprefix("prov_"))
	proveedor = _proveedor_o_404(db, proveedor_id)
	return documentos_proveedor_a_dict(
		proveedor,
		repo.listar_documentos(db, proveedor.id),
		incluir_proveedor_id=True,
	)


def _documentos_vencidos_por_tipo(
	db: Session, proveedor: Proveedor, hoy: date
) -> list[str]:
	perfil = repo.obtener_perfil(db, proveedor.id)
	if perfil is None:
		return []
	tipos_vencidos = []
	documentos = repo.listar_documentos(db, proveedor.id)
	for requisito in repo.listar_requisitos(db, perfil.tipo_proveedor):
		if not requisito.exige_vigencia:
			continue
		if any(
			documento.tipo_documento == requisito.tipo_documento
			and documento.estado == "VENCIDO"
			and documento.fecha_vencimiento is not None
			and documento.fecha_vencimiento < hoy
			for documento in documentos
		):
			tipos_vencidos.append(requisito.tipo_documento)
	return tipos_vencidos


def _cumple_requisitos(db: Session, proveedor: Proveedor, hoy: date) -> bool:
	perfil = repo.obtener_perfil(db, proveedor.id)
	if perfil is None:
		return False
	requisitos = repo.listar_requisitos(db, perfil.tipo_proveedor)
	if not requisitos:
		return False
	documentos = repo.listar_documentos(db, proveedor.id)
	return all(
		any(
			documento.tipo_documento == requisito.tipo_documento
			and documento.estado == "APROBADO"
			and (
				not requisito.exige_vigencia
				or (
					documento.fecha_vencimiento is not None
					and documento.fecha_vencimiento >= hoy
				)
			)
			for documento in documentos
		)
		for requisito in requisitos
	)


def procesar_vencimientos(db: Session, hoy: date | None = None) -> dict[str, int]:
	"""Marca vencimientos obligatorios, suspende proveedores y audita una sola vez."""
	fecha_actual = hoy or datetime.now(ZONA).date()
	documentos_vencidos = 0
	proveedores_suspendidos = 0
	auditorias_registradas = 0

	for proveedor in repo.listar_proveedores(db):
		perfil = repo.obtener_perfil(db, proveedor.id)
		if perfil is None:
			continue
		requisitos = {
			requisito.tipo_documento: requisito
			for requisito in repo.listar_requisitos(db, perfil.tipo_proveedor)
			if requisito.exige_vigencia
		}
		documentos = repo.listar_documentos(db, proveedor.id)
		documentos_auditar = []
		for documento in documentos:
			requisito = requisitos.get(documento.tipo_documento)
			if (
				requisito is None
				or documento.fecha_vencimiento is None
				or documento.fecha_vencimiento >= fecha_actual
				or documento.estado not in {"APROBADO", "VENCIDO"}
			):
				continue
			if documento.estado == "APROBADO":
				documento.estado = "VENCIDO"
				documentos_vencidos += 1
			documentos_auditar.append(documento)

		for documento in documentos_auditar:
			if repo.obtener_auditoria_documento(
				db, documento.id, EVENTO_DOCUMENTO_VENCIDO
			) is None:
				repo.agregar_auditoria(
					db,
					AuditoriaDocumento(
						proveedor_id=proveedor.id,
						documento_id=documento.id,
						evento=EVENTO_DOCUMENTO_VENCIDO,
						registrada_en=datetime.now(ZONA),
						detalle=(
							"Documento obligatorio vencido: "
							f"{documento.tipo_documento}"
						),
					),
				)
				auditorias_registradas += 1

		tipos_vencidos = _documentos_vencidos_por_tipo(
			db, proveedor, fecha_actual
		)
		if (
			tipos_vencidos
			and not _cumple_requisitos(db, proveedor, fecha_actual)
			and (
				proveedor.estado_habilitacion != "SUSPENDIDO"
				or proveedor.estado_operativo != "NO_DISPONIBLE"
				or proveedor.motivo_habilitacion
				!= "Documento obligatorio vencido: " + ", ".join(tipos_vencidos)
			)
		):
			proveedor.estado_habilitacion = "SUSPENDIDO"
			proveedor.estado_operativo = "NO_DISPONIBLE"
			proveedor.motivo_habilitacion = (
				"Documento obligatorio vencido: " + ", ".join(tipos_vencidos)
			)
			proveedores_suspendidos += 1

	if documentos_vencidos or auditorias_registradas or proveedores_suspendidos:
		db.commit()
	return {
		"documentosVencidos": documentos_vencidos,
		"proveedoresSuspendidos": proveedores_suspendidos,
		"auditoriasRegistradas": auditorias_registradas,
	}


def main() -> None:
	with SessionLocal() as db:
		resultado = procesar_vencimientos(db)
	print(
		"Revisión HU-16 completada: "
		f"{resultado['documentosVencidos']} documentos vencidos, "
		f"{resultado['proveedoresSuspendidos']} proveedores suspendidos, "
		f"{resultado['auditoriasRegistradas']} auditorías nuevas."
	)


if __name__ == "__main__":
	main()
