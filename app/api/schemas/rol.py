"""Esquemas de entrada y salida de roles."""
from pydantic import BaseModel, Field

from app.domain.rol import Rol


class RolEntrada(BaseModel):
	codigo: str = Field(min_length=2, max_length=50, pattern=r"^[A-Z0-9_]+$")
	nombre: str = Field(min_length=2, max_length=100)
	descripcion: str | None = Field(default=None, max_length=255)
	activo: bool = True


def rol_a_dict(rol: Rol) -> dict:
	return {
		"rolId": rol.rol_id,
		"codigo": rol.codigo,
		"nombre": rol.nombre,
		"descripcion": rol.descripcion,
		"activo": rol.activo,
	}
