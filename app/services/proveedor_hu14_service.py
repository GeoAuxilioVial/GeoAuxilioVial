"""Reglas de negocio para el registro y revisión documental (HU-14)."""
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.proveedor_hu14_schemas import (
	DocumentoProveedorEntrada,
	RegistroProveedorEntrada,
	RevisionDocumentoEntrada,
)
from app.core.errors import ErrorNegocio, ZONA
from app.domain.documentos_requeridos_domain import TIPOS_PROVEEDOR
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import (
	DatosProveedor,
	DocumentoProveedor,
	ProveedorZonaCobertura,
)
from app.repositories import proveedor_hu14_repository as repo


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
		raise ErrorNegocio(401, "Autenticación requerida o token inválido")
	return int(sub.removeprefix("usr_"))


def _id_publico(valor: str, prefijo: str) -> int:
	if not re.fullmatch(rf"{prefijo}_[0-9]+", valor):
		raise ErrorNegocio(404, "Recurso no encontrado")
	return int(valor.removeprefix(f"{prefijo}_"))


def _validar_tipo_proveedor(db: Session, tipo_proveedor: str):
	requisitos = repo.obtener_requisitos(db, tipo_proveedor)
	if tipo_proveedor not in TIPOS_PROVEEDOR or not requisitos:
		raise _error_validacion(
			"tipoProveedor",
			"VALOR_FUERA_DE_CATALOGO",
			"El tipo de proveedor no tiene documentos requeridos configurados",
		)
	return requisitos


def registrar(db: Session, payload: dict, datos: RegistroProveedorEntrada) -> dict:
	usuario_id = _usuario_id(payload)
	usuario = repo.obtener_usuario(db, usuario_id)
	if usuario is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	if repo.obtener_proveedor_por_usuario(db, usuario_id) is not None:
		raise ErrorNegocio(
			409,
			"El usuario ya tiene un perfil de proveedor registrado",
			{"codigo": "PROVEEDOR_YA_REGISTRADO"},
		)

	requisitos = _validar_tipo_proveedor(db, datos.tipo_proveedor)
	if len(set(datos.zonas_cobertura)) != len(datos.zonas_cobertura):
		raise _error_validacion(
			"zonasCobertura",
			"FORMATO_INVALIDO",
			"No se deben repetir las zonas de cobertura",
		)
	zonas = []
	for zona_id in datos.zonas_cobertura:
		if not re.fullmatch(r"zon_[0-9]+", zona_id):
			raise _error_validacion(
				"zonasCobertura",
				"VALOR_FUERA_DE_CATALOGO",
				"La zona no existe o no está activa",
			)
		id_zona = _id_publico(zona_id, "zon")
		zona = repo.obtener_zona(db, id_zona)
		if zona is None or not zona.activa:
			raise _error_validacion(
				"zonasCobertura",
				"VALOR_FUERA_DE_CATALOGO",
				"La zona no existe o no está activa",
			)
		zonas.append(zona)

	proveedor = Proveedor(usuario_id=usuario_id, estado_habilitacion="PENDIENTE")
	try:
		repo.agregar_proveedor(db, proveedor)
		db.add(
			DatosProveedor(
				proveedor_id=proveedor.id,
				nombre_comercial=datos.nombre_comercial,
				tipo_proveedor=datos.tipo_proveedor,
			)
		)
		for zona in zonas:
			db.add(
				ProveedorZonaCobertura(
					proveedor_id=proveedor.id,
					zona_id=zona.id,
				)
			)
		roles = usuario.lista_roles()
		if "PROVEEDOR" not in roles:
			roles.append("PROVEEDOR")
		usuario.roles = ",".join(roles)
		db.commit()
		db.refresh(proveedor)
	except IntegrityError:
		db.rollback()
		if repo.obtener_proveedor_por_usuario(db, usuario_id) is not None:
			raise ErrorNegocio(
				409,
				"El usuario ya tiene un perfil de proveedor registrado",
				{"codigo": "PROVEEDOR_YA_REGISTRADO"},
			)
		raise

	perfil = repo.obtener_datos_proveedor(db, proveedor.id)
	return {
		"proveedor": proveedor,
		"perfil": perfil,
		"zonas": [zona.zona_id for zona in zonas],
		"requisitos": requisitos,
	}


def cargar_documento(
	db: Session,
	payload: dict,
	datos: DocumentoProveedorEntrada,
) -> DocumentoProveedor:
	roles = _roles(payload)
	if "PROVEEDOR" not in roles:
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")

	usuario_id = _usuario_id(payload)
	proveedor = repo.obtener_proveedor_por_usuario(db, usuario_id)
	perfil = (
		repo.obtener_datos_proveedor(db, proveedor.id)
		if proveedor is not None
		else None
	)
	if proveedor is None or perfil is None:
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")

	requisitos = _validar_tipo_proveedor(db, perfil.tipo_proveedor)
	requisito = next(
		(item for item in requisitos if item.tipo_documento == datos.tipo_documento),
		None,
	)
	if requisito is None:
		raise _error_validacion(
			"tipoDocumento",
			"VALOR_FUERA_DE_CATALOGO",
			"El tipo de documento no es requerido para este proveedor",
		)

	if not re.fullmatch(r"file_[A-Za-z0-9][A-Za-z0-9_-]*", datos.archivo_id):
		raise _error_validacion(
			"archivoId",
			"ARCHIVO_INVALIDO",
			"La referencia del archivo no es válida",
		)
	archivo = repo.obtener_archivo(db, datos.archivo_id)
	if archivo is None or archivo.proveedor_id != proveedor.id or not archivo.valido:
		raise _error_validacion(
			"archivoId",
			"ARCHIVO_INVALIDO",
			"El archivo no existe, no pertenece al usuario o no es válido",
		)

	hoy = datetime.now(ZONA).date()
	if requisito.exige_vigencia and datos.fecha_vencimiento is None:
		raise _error_validacion(
			"fechaVencimiento",
			"CAMPO_OBLIGATORIO",
			"La fecha de vencimiento es obligatoria para este documento",
		)
	if (
		requisito.exige_vigencia
		and datos.fecha_vencimiento is not None
		and datos.fecha_vencimiento <= hoy
	):
		raise _error_validacion(
			"fechaVencimiento",
			"DOCUMENTO_VENCIDO",
			"La fecha de vencimiento debe ser posterior a hoy",
		)

	reemplaza_id = None
	if datos.reemplaza_documento_id is not None:
		reemplaza_id = _id_publico(datos.reemplaza_documento_id, "doc")
		documento_anterior = repo.obtener_documento(db, reemplaza_id)
		if (
			documento_anterior is None
			or documento_anterior.proveedor_id != proveedor.id
			or documento_anterior.tipo_documento != datos.tipo_documento
		):
			raise _error_validacion(
				"reemplazaDocumentoId",
				"VALOR_FUERA_DE_CATALOGO",
				"El documento a reemplazar debe pertenecer al proveedor y ser del mismo tipo",
			)

	documento = DocumentoProveedor(
		proveedor_id=proveedor.id,
		archivo_id=archivo.archivo_id,
		tipo_documento=datos.tipo_documento,
		fecha_vencimiento=datos.fecha_vencimiento,
		estado="PENDIENTE_REVISION",
		creado_en=datetime.now(ZONA),
		reemplaza_documento_id=reemplaza_id,
	)
	repo.agregar_documento(db, documento)
	return documento


def _proveedor_habilitado(db: Session, proveedor: Proveedor) -> bool:
	perfil = repo.obtener_datos_proveedor(db, proveedor.id)
	if perfil is None:
		return False
	requisitos = repo.obtener_requisitos(db, perfil.tipo_proveedor)
	if not requisitos:
		return False

	hoy = datetime.now(ZONA).date()
	for requisito in requisitos:
		documentos = repo.obtener_documentos(
			db, proveedor.id, requisito.tipo_documento
		)
		if not any(
			documento.estado == "APROBADO"
			and (
				not requisito.exige_vigencia
				or (
					documento.fecha_vencimiento is not None
					and documento.fecha_vencimiento > hoy
				)
			)
			for documento in documentos
		):
			return False
	return True


def revisar_documento(
	db: Session,
	payload: dict,
	proveedor_publico_id: str,
	documento_publico_id: str,
	datos: RevisionDocumentoEntrada,
) -> dict:
	if not set(_roles(payload)).intersection({"REVISOR", "ADMINISTRADOR"}):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")
	revisor_id = _usuario_id(payload)
	if datos.decision not in {"APROBADO", "RECHAZADO"}:
		raise _error_validacion(
			"decision",
			"VALOR_FUERA_DE_CATALOGO",
			"La decisión debe ser APROBADO o RECHAZADO",
		)
	motivo = datos.motivo.strip() if datos.motivo is not None else None
	if datos.decision == "RECHAZADO" and not motivo:
		raise _error_validacion(
			"motivo",
			"MOTIVO_OBLIGATORIO",
			"El rechazo requiere un motivo",
		)

	proveedor_id = _id_publico(proveedor_publico_id, "prov")
	documento_id = _id_publico(documento_publico_id, "doc")
	proveedor = repo.obtener_proveedor(db, proveedor_id)
	documento = repo.obtener_documento(db, documento_id)
	if (
		proveedor is None
		or documento is None
		or documento.proveedor_id != proveedor.id
	):
		raise ErrorNegocio(404, "Recurso no encontrado")
	if documento.estado != "PENDIENTE_REVISION":
		raise ErrorNegocio(
			409,
			"El documento ya fue revisado y no admite una nueva decisión",
			{"codigo": "DOCUMENTO_YA_REVISADO"},
		)

	documento.estado = datos.decision
	documento.revisor_usuario_id = revisor_id
	documento.revisado_en = datetime.now(ZONA)
	documento.motivo = motivo or None
	if datos.decision == "APROBADO" and documento.reemplaza_documento_id is not None:
		anterior = repo.obtener_documento(db, documento.reemplaza_documento_id)
		if anterior is not None:
			anterior.estado = "REEMPLAZADO"

	proveedor.estado_habilitacion = (
		"HABILITADO" if _proveedor_habilitado(db, proveedor) else "PENDIENTE"
	)
	db.commit()
	db.refresh(documento)
	return {
		"documento": documento,
		"estado_habilitacion": proveedor.estado_habilitacion,
		"proveedor_habilitado": proveedor.estado_habilitacion == "HABILITADO",
	}
