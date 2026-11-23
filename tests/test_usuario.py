import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
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
