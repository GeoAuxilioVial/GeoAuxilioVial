"""Acceso a datos de usuarios."""
from sqlalchemy.orm import Session

from app.domain.usuario_domain import Usuario


def obtener_por_correo(db: Session, correo: str) -> Usuario | None:
	return db.query(Usuario).filter(Usuario.correo == correo).first()


def guardar(db: Session, usuario: Usuario) -> Usuario:
	db.add(usuario)
	db.commit()
	db.refresh(usuario)
	return usuario
