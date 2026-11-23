"""Esquemas de entrada y salida de usuarios."""
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.usuario_domain import Usuario


CORREO_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistroEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid")

	nombre: str = Field(min_length=2, max_length=100)
	correo: str = Field(min_length=3, max_length=255)
	password: str = Field(min_length=8, max_length=255)
	telefono: str | None = Field(default=None, max_length=30)

	@field_validator("correo")
	@classmethod
	def validar_correo(cls, valor: str) -> str:
		if not CORREO_RE.match(valor):
			raise ValueError("El correo no tiene un formato valido")
		return valor.strip().lower()

	@field_validator("password")
	@classmethod
	def validar_password(cls, valor: str) -> str:
		if len(valor) < 8 or not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
			raise ValueError("La contraseña debe tener al menos 8 caracteres con letras y numeros")
		return valor


class LoginEntrada(BaseModel):
	model_config = ConfigDict(extra="forbid")

	correo: str = Field(min_length=3, max_length=255)
	password: str = Field(min_length=1, max_length=255)

	@field_validator("correo")
	@classmethod
	def normalizar_correo(cls, valor: str) -> str:
		if not CORREO_RE.match(valor):
			raise ValueError("El correo no tiene un formato valido")
		return valor.strip().lower()


class PerfilActualizacion(BaseModel):
	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	nombre: str = Field(min_length=2, max_length=100)
	telefono: str = Field(
		min_length=7,
		max_length=16,
		pattern=r"^\+?[1-9]\d{6,14}$",
	)


def usuario_a_dict(usuario: Usuario) -> dict:
	return {
		"id": usuario.usuario_id,
		"nombre": usuario.nombre,
		"correo": usuario.correo,
		"roles": usuario.lista_roles(),
	}


def perfil_a_dict(usuario: Usuario) -> dict:
	return {
		**usuario_a_dict(usuario),
		"telefono": usuario.telefono,
	}
