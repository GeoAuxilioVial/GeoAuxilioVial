import datetime as dt
import re
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.domain.rol import Rol
from app.domain.usuario_domain import Usuario
from app.services.usuario_service import limpiar_intentos
from main import app


client = TestClient(app)
REGISTRO = "/api/v1/auth/registro"
LOGIN = "/api/v1/auth/login"


def _datos(correo="hu08@example.com", password="ClaveSegura123"):
	return {
		"nombre": "Usuario HU08",
		"correo": correo,
		"password": password,
		"telefono": "+573001112233",
	}


@pytest.fixture(autouse=True)
def limpiar_datos_hu08():
	limpiar_intentos()
	with SessionLocal() as db:
		for usuario in db.query(Usuario).filter(Usuario.correo.like("hu08%")).all():
			db.delete(usuario)
		db.commit()
	yield
	limpiar_intentos()
	with SessionLocal() as db:
		for usuario in db.query(Usuario).filter(Usuario.correo.like("hu08%")).all():
			db.delete(usuario)
		db.commit()


def test_registro_valido():
	r = client.post(REGISTRO, json=_datos())
	assert r.status_code == 201
	assert r.json()["exito"] is True
	assert r.json()["datos"]["usuario"]["id"].startswith("usr_")
	assert r.json()["datos"]["usuario"]["roles"] == ["CLIENTE"]
	assert "password" not in r.text
	assert "password_hash" not in r.text
	assert "token" not in r.json()["datos"]


def test_login_valido():
	client.post(REGISTRO, json=_datos())
	r = client.post(LOGIN, json={"correo": "hu08@example.com", "password": "ClaveSegura123"})
	assert r.status_code == 200
	assert r.json()["datos"]["tipoToken"] == "Bearer"
	assert r.json()["datos"]["expiraEn"] > 0
	assert r.json()["datos"]["token"]
	assert "password" not in r.text
	assert "password_hash" not in r.text


@pytest.mark.parametrize(
	"body,campo_ausente",
	[
		({"correo": "hu08.faltante@example.com"}, "password"),
		({"password": "ClaveSegura123"}, "correo"),
	],
)
def test_login_requiere_correo_y_password(body, campo_ausente):
	respuesta = client.post(LOGIN, json=body)

	assert respuesta.status_code == 422
	error = respuesta.json()["datos"]["errores"][0]
	assert error["codigo"] == "CAMPO_OBLIGATORIO"
	assert error["campo"] == campo_ausente


def test_token_emitido_tiene_firma_valida_expiracion_y_se_rechaza_altera_o_expirado():
	client.post(REGISTRO, json=_datos(correo="hu08.jwt-expira@example.com"))
	login = client.post(
		LOGIN,
		json={"correo": "hu08.jwt-expira@example.com", "password": "ClaveSegura123"},
	)
	token = login.json()["datos"]["token"]
	payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
	ahora = dt.datetime.now(dt.timezone.utc).timestamp()

	assert login.status_code == 200
	assert payload["exp"] > ahora
	assert payload["sub"].startswith("usr_")
	assert payload["roles"] == ["CLIENTE"]

	acceso = client.get(
		"/api/v1/perfil",
		headers={"Authorization": f"Bearer {token}"},
	)
	assert acceso.status_code == 200

	cabecera, cuerpo, firma = token.split(".")
	firma_alterada = ("A" if firma[0] != "A" else "B") + firma[1:]
	token_alterado = f"{cabecera}.{cuerpo}.{firma_alterada}"
	rechazado = client.get(
		"/api/v1/perfil",
		headers={"Authorization": f"Bearer {token_alterado}"},
	)
	assert rechazado.status_code == 401
	assert rechazado.json()["mensaje"] == "Autenticación requerida o token inválido"

	payload["exp"] = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
	token_expirado = jwt.encode(payload, settings.secret_key, algorithm="HS256")
	rechazado = client.get(
		"/api/v1/perfil",
		headers={"Authorization": f"Bearer {token_expirado}"},
	)
	assert rechazado.status_code == 401
	assert rechazado.json()["mensaje"] == "Autenticación requerida o token inválido"


def test_identificadores_de_usuario_se_generan_y_son_unicos():
	primero = client.post(
		REGISTRO,
		json=_datos(correo=f"hu08.id-{uuid.uuid4().hex}@example.com"),
	)
	segundo = client.post(
		REGISTRO,
		json=_datos(correo=f"hu08.id-{uuid.uuid4().hex}@example.com"),
	)

	id_primero = primero.json()["datos"]["usuario"]["id"]
	id_segundo = segundo.json()["datos"]["usuario"]["id"]

	assert primero.status_code == 201
	assert segundo.status_code == 201
	assert re.fullmatch(r"usr_[0-9]+", id_primero)
	assert re.fullmatch(r"usr_[0-9]+", id_segundo)
	assert id_primero != id_segundo


def test_registro_y_catalogo_usan_roles_vigentes():
	with SessionLocal() as db:
		cliente = db.query(Rol).filter_by(codigo="CLIENTE").one()
		revisor = db.query(Rol).filter_by(codigo="REVISOR").one()
		assert cliente.activo is True
		assert revisor.activo is True

	respuesta = client.post(REGISTRO, json=_datos(correo="hu08.rn-p01@example.com"))

	assert respuesta.status_code == 201
	assert respuesta.json()["datos"]["usuario"]["roles"] == [cliente.codigo]


def test_token_de_login_funciona_en_modulos_dependientes():
	client.post(REGISTRO, json=_datos(correo="hu08.modulos@example.com"))
	login = client.post(
		LOGIN,
		json={"correo": "hu08.modulos@example.com", "password": "ClaveSegura123"},
	)
	headers = {"Authorization": f"Bearer {login.json()['datos']['token']}"}

	perfil = client.get("/api/v1/perfil", headers=headers)
	documentos = client.get(
		"/api/v1/parametros/documentos-requeridos",
		params={"tipoProveedor": "GRUA"},
		headers=headers,
	)

	assert login.status_code == 200
	assert perfil.status_code == 200
	assert perfil.json()["datos"]["correo"] == "hu08.modulos@example.com"
	assert documentos.status_code == 200


def test_login_password_incorrecta():
	client.post(REGISTRO, json=_datos())
	r = client.post(LOGIN, json={"correo": "hu08@example.com", "password": "OtraClave123"})
	assert r.status_code == 401
	assert r.json()["mensaje"] == "Credenciales inválidas"
	assert r.json()["datos"] is None
	assert "token" not in r.text


def test_login_cuenta_inexistente_mismo_mensaje():
	r = client.post(LOGIN, json={"correo": "hu08.inexistente@example.com", "password": "ClaveSegura123"})
	assert r.status_code == 401
	assert r.json()["mensaje"] == "Credenciales inválidas"
	assert r.json()["datos"] is None


def test_registro_correo_invalido():
	r = client.post(REGISTRO, json=_datos(correo="ana"))
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "FORMATO_INVALIDO"
	assert r.json()["datos"]["errores"][0]["campo"] == "correo"


def test_registro_password_ausente():
	datos = _datos()
	datos.pop("password")
	r = client.post(REGISTRO, json=datos)
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "CAMPO_OBLIGATORIO"


def test_registro_json_mal_formado():
	r = client.post(REGISTRO, content=b"{", headers={"Content-Type": "application/json"})
	assert r.status_code == 400
	assert r.json()["mensaje"] == "Solicitud mal formada"


def test_registro_intento_asignar_rol():
	datos = _datos()
	datos["roles"] = ["ADMINISTRADOR"]
	r = client.post(REGISTRO, json=datos)
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "CAMPO_NO_EDITABLE"


def test_registro_correo_duplicado():
	client.post(REGISTRO, json=_datos(correo="hu08.duplicado@example.com"))
	r = client.post(REGISTRO, json=_datos(correo="HU08.DUPLICADO@example.com"))
	assert r.status_code == 409
	assert r.json()["datos"]["codigo"] == "CORREO_DUPLICADO"


def test_limite_intentos_login():
	r = None
	for _ in range(5):
		r = client.post(LOGIN, json={"correo": "hu08.limite@example.com", "password": "OtraClave123"})
	assert r is not None
	assert r.status_code == 429
	assert r.json()["datos"]["codigo"] == "LIMITE_INTENTOS_EXCEDIDO"
	assert "token" not in r.text


def test_password_debil():
	r = client.post(REGISTRO, json=_datos(correo="hu08.debil@example.com", password="solamente"))
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["campo"] == "password"
	assert r.json()["datos"]["errores"][0]["codigo"] == "FORMATO_INVALIDO"


def test_jwt_roles_lista():
	client.post(REGISTRO, json=_datos(correo="hu08.jwt@example.com"))
	r = client.post(LOGIN, json={"correo": "hu08.jwt@example.com", "password": "ClaveSegura123"})
	payload = jwt.decode(
		r.json()["datos"]["token"],
		settings.secret_key,
		algorithms=["HS256"],
	)
	assert payload["roles"] == ["CLIENTE"]
