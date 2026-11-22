"""Reglas de negocio de registro e inicio de sesion."""
import datetime as dt
from collections import defaultdict

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorNegocio
from app.domain.usuario_domain import Usuario
from app.repositories import usuario_repository as repo
from app.api.schemas.usuario_schemas import LoginEntrada, RegistroEntrada

MAX_INTENTOS_FALLIDOS = 5
_intentos_fallidos: dict[str, list[dt.datetime]] = defaultdict(list)


def _limpiar_intentos(correo: str) -> None:
	corte = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=15)
	_intentos_fallidos[correo] = [
		fecha for fecha in _intentos_fallidos[correo] if fecha > corte
	]


def registrar(db: Session, datos: RegistroEntrada) -> Usuario:
	correo = datos.correo.strip().lower()
	if repo.obtener_por_correo(db, correo):
		raise ErrorNegocio(
			409,
			"Ya existe una cuenta con el correo indicado",
			{"codigo": "CORREO_DUPLICADO"},
		)
	password_hash = bcrypt.hashpw(datos.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
	usuario = Usuario(
		nombre=datos.nombre,
		correo=correo,
		password_hash=password_hash,
		telefono=datos.telefono,
		roles="CLIENTE",
	)
	return repo.guardar(db, usuario)


def iniciar_sesion(db: Session, datos: LoginEntrada) -> dict:
	correo = datos.correo.strip().lower()
	_limpiar_intentos(correo)
	if len(_intentos_fallidos[correo]) >= MAX_INTENTOS_FALLIDOS:
		raise ErrorNegocio(
			429,
			"Demasiados intentos. Intente nuevamente más tarde",
			{"codigo": "LIMITE_INTENTOS_EXCEDIDO"},
		)

	usuario = repo.obtener_por_correo(db, correo)
	credenciales_validas = bool(
		usuario
		and bcrypt.checkpw(datos.password.encode("utf-8"), usuario.password_hash.encode("utf-8"))
	)
	if not credenciales_validas:
		_intentos_fallidos[correo].append(dt.datetime.now(dt.timezone.utc))
		_limpiar_intentos(correo)
		if len(_intentos_fallidos[correo]) >= MAX_INTENTOS_FALLIDOS:
			raise ErrorNegocio(
				429,
				"Demasiados intentos. Intente nuevamente más tarde",
				{"codigo": "LIMITE_INTENTOS_EXCEDIDO"},
			)
		raise ErrorNegocio(401, "Credenciales inválidas")

	_intentos_fallidos.pop(correo, None)
	expira_en = settings.access_token_expire_minutes * 60
	expiracion = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=expira_en)
	token = jwt.encode(
		{
			"sub": usuario.usuario_id,
			"roles": usuario.lista_roles(),
			"rol": usuario.lista_roles()[0],
			"exp": expiracion,
		},
		settings.secret_key,
		algorithm="HS256",
	)
	return {
		"usuario": usuario,
		"token": token,
		"tipoToken": "Bearer",
		"expiraEn": expira_en,
	}


def limpiar_intentos() -> None:
	_intentos_fallidos.clear()
