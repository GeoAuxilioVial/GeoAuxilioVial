"""Acceso a datos del catálogo de roles."""
from sqlalchemy.orm import Session

from app.domain.rol import Rol


def listar(db: Session) -> list[Rol]:
    return db.query(Rol).order_by(Rol.id).all()


def obtener(db: Session, id_: int) -> Rol | None:
    return db.get(Rol, id_)


def obtener_por_codigo(db: Session, codigo: str) -> Rol | None:
    return db.query(Rol).filter(Rol.codigo == codigo).first()


def guardar(db: Session, rol: Rol) -> Rol:
    db.add(rol)
    db.commit()
    db.refresh(rol)
    return rol


def eliminar(db: Session, rol: Rol) -> None:
    db.delete(rol)
    db.commit()


def contar_usuarios_activos(db: Session, id_: int) -> int:
    # TODO: cuando exista la tabla de usuarios (MOD-01), contar aquí los usuarios activos con este rol.
    return 0
