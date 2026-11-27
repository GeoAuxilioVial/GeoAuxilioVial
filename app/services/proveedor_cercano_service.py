"""Reglas de búsqueda geográfica de proveedores (HU-18)."""
import math
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.schemas.proveedor_cercano_schemas import proveedor_cercano_a_dict
from app.core.config import settings
from app.core.errors import ErrorNegocio, ZONA
from app.domain.documentos_requeridos_domain import TIPOS_PROVEEDOR
from app.domain.zonas_cobertura_domain import distancia_km
from app.repositories import proveedor_cercano_repository as repo


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


def _ubicacion_vigente(actualizada_en: datetime, ahora: datetime) -> bool:
	if actualizada_en.tzinfo is None:
		actualizada_en = actualizada_en.replace(tzinfo=ZONA)
	edad_segundos = (ahora - actualizada_en).total_seconds()
	return (
		0 <= edad_segundos
		<= settings.ubicacion_frescura_minutos * 60
	)


def buscar_cercanos(
	db: Session,
	payload: dict,
	latitud: float,
	longitud: float,
	tipo_servicio: str,
	radio_km: float,
) -> dict:
	if not set(_roles(payload)).intersection({"CLIENTE", "ADMINISTRADOR"}):
		raise ErrorNegocio(403, "No tiene permisos para realizar esta operación")

	if not math.isfinite(latitud) or not -90 <= latitud <= 90:
		raise _error_validacion(
			"latitud", "FUERA_DE_RANGO", "La latitud debe estar entre -90 y 90"
		)
	if not math.isfinite(longitud) or not -180 <= longitud <= 180:
		raise _error_validacion(
			"longitud",
			"FUERA_DE_RANGO",
			"La longitud debe estar entre -180 y 180",
		)
	if (
		not math.isfinite(radio_km)
		or radio_km <= 0
		or radio_km > settings.radio_busqueda_max_km
	):
		raise _error_validacion(
			"radioKm",
			"FUERA_DE_RANGO",
			f"El radioKm debe ser mayor que 0 y no superar {settings.radio_busqueda_max_km:g} km",
		)
	if tipo_servicio not in TIPOS_PROVEEDOR:
		raise _error_validacion(
			"tipoServicio",
			"VALOR_FUERA_DE_CATALOGO",
			"El tipoServicio no pertenece al catálogo de tipos de proveedor",
		)

	ahora = datetime.now(ZONA)
	resultados: dict[int, tuple[float, dict]] = {}
	for proveedor, perfil, zona in repo.listar_candidatos(db, tipo_servicio):
		if proveedor.latitud is None or proveedor.longitud is None:
			continue
		if proveedor.actualizada_en is None or not _ubicacion_vigente(
			proveedor.actualizada_en, ahora
		):
			continue
		if not zona.cubre_punto(latitud, longitud):
			continue

		distancia = distancia_km(
			latitud, longitud, proveedor.latitud, proveedor.longitud
		)
		if distancia > radio_km or proveedor.id in resultados:
			continue
		resultados[proveedor.id] = (
			distancia,
			proveedor_cercano_a_dict(proveedor, perfil, distancia),
		)

	proveedores = [
		resultado
		for _, resultado in sorted(
			resultados.values(),
			key=lambda candidato: (
				candidato[0],
				candidato[1]["id"],
			),
		)
	]
	return {"proveedores": proveedores}
