"""Reglas de negocio de las zonas de cobertura (HU-03)."""
from sqlalchemy.orm import Session

from app.api.schemas.zonas_cobertura_schemas import ZonaEntrada
from app.core.errors import ErrorNegocio
from app.domain.zonas_cobertura_domain import ZonaCobertura
from app.repositories import zonas_cobertura_repository as repo


def _parsear_id(zona_id: str) -> int:
	try:
		return int(zona_id.replace("zon_", ""))
	except ValueError:
		raise ErrorNegocio(404, "Recurso no encontrado")


def _obtener_o_404(db: Session, zona_id: str) -> ZonaCobertura:
	zona = repo.obtener(db, _parsear_id(zona_id))
	if zona is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	return zona


def listar(db: Session, activa: bool | None = None) -> list[ZonaCobertura]:
	return repo.listar(db, activa)


def obtener(db: Session, zona_id: str) -> ZonaCobertura:
	return _obtener_o_404(db, zona_id)


def crear(db: Session, datos: ZonaEntrada) -> ZonaCobertura:
	if repo.obtener_por_nombre(db, datos.nombre):
		raise ErrorNegocio(409, "Ya existe una zona de cobertura con ese nombre")
	return repo.guardar(db, ZonaCobertura(**datos.model_dump()))


def actualizar(db: Session, zona_id: str, datos: ZonaEntrada) -> ZonaCobertura:
	zona = _obtener_o_404(db, zona_id)
	otra = repo.obtener_por_nombre(db, datos.nombre)
	if otra and otra.id != zona.id:
		raise ErrorNegocio(409, "Ya existe una zona de cobertura con ese nombre")
	for campo, valor in datos.model_dump().items():
		setattr(zona, campo, valor)
	return repo.guardar(db, zona)


def eliminar(db: Session, zona_id: str) -> str:
	zona = _obtener_o_404(db, zona_id)
	if repo.contar_proveedores_asociados(db, zona.id) > 0:
		raise ErrorNegocio(409, "No se puede eliminar la zona porque tiene proveedores asociados")  # RN-09
	identificador = zona.zona_id
	repo.eliminar(db, zona)
	return identificador
