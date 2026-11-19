"""Reglas de negocio del catálogo de roles (HU-01)."""
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.errors import ErrorNegocio
from app.domain.rol import Rol
from app.repositories import rol_repository as repo
from app.api.schemas.rol import RolEntrada

ROLES_BASE = [
	("ADMINISTRADOR", "Administrador", "Gestiona la configuración del sistema"),
	("CLIENTE", "Cliente", "Solicita servicios de auxilio vial"),
	("PROVEEDOR", "Proveedor", "Prestador de servicios de auxilio vial"),
]


def inicializar_catalogo() -> None:
	"""Crea las tablas y siembra los roles base si no existen."""
	Base.metadata.create_all(bind=engine)
	with SessionLocal() as db:
		for codigo, nombre, descripcion in ROLES_BASE:
			if not repo.obtener_por_codigo(db, codigo):
				db.add(Rol(codigo=codigo, nombre=nombre, descripcion=descripcion, activo=True))
		db.commit()


def _parsear_id(rol_id: str) -> int:
	try:
		return int(rol_id.replace("rol_", ""))
	except ValueError:
		raise ErrorNegocio(404, "Recurso no encontrado")


def _obtener_o_404(db: Session, rol_id: str) -> Rol:
	rol = repo.obtener(db, _parsear_id(rol_id))
	if rol is None:
		raise ErrorNegocio(404, "Recurso no encontrado")
	return rol


def listar(db: Session) -> list[Rol]:
	return repo.listar(db)


def crear(db: Session, datos: RolEntrada) -> Rol:
	if repo.obtener_por_codigo(db, datos.codigo):
		raise ErrorNegocio(409, "Ya existe un rol con ese código")
	return repo.guardar(db, Rol(**datos.model_dump()))


def actualizar(db: Session, rol_id: str, datos: RolEntrada) -> Rol:
	rol = _obtener_o_404(db, rol_id)
	otro = repo.obtener_por_codigo(db, datos.codigo)
	if otro and otro.id != rol.id:
		raise ErrorNegocio(409, "Ya existe un rol con ese código")
	for campo, valor in datos.model_dump().items():
		setattr(rol, campo, valor)
	return repo.guardar(db, rol)


def eliminar(db: Session, rol_id: str) -> None:
	rol = _obtener_o_404(db, rol_id)
	if repo.contar_usuarios_activos(db, rol.id) > 0:
		raise ErrorNegocio(409, "El rol está en uso por registros activos y no puede eliminarse")  # RN-09
	repo.eliminar(db, rol)
