import datetime as dt
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.domain.usuario_domain import Usuario
from main import app


client = TestClient(app)
PERFIL = "/api/v1/perfil"


def _token(
	usuario_id: int,
	expiracion: dt.datetime | None = None,
	roles: list[str] | None = None,
) -> str:
	roles_emitidos = roles or ["CLIENTE"]
	return jwt.encode(
		{
			"sub": f"usr_{usuario_id:03d}",
			"roles": roles_emitidos,
			"rol": roles_emitidos[0],
			"exp": expiracion or dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
		},
		settings.secret_key,
		algorithm="HS256",
	)


@pytest.fixture
def perfil_hu09():
	identificador = uuid.uuid4().hex
	correo = f"hu09.{identificador}@example.com"
	correo_otro = f"hu09.otro.{identificador}@example.com"
	with SessionLocal() as db:
		usuario = Usuario(
			nombre="Usuario HU09",
			correo=correo,
			password_hash="hash-no-utilizado",
			telefono="+573001112233",
			roles="CLIENTE",
		)
		otro_usuario = Usuario(
			nombre="Otro HU09",
			correo=correo_otro,
			password_hash="hash-no-utilizado",
			telefono="+573004445566",
			roles="PROVEEDOR",
		)
		db.add_all([usuario, otro_usuario])
		db.commit()
		db.refresh(usuario)
		db.refresh(otro_usuario)
		datos = {
			"id": usuario.id,
			"otro_id": otro_usuario.id,
			"token": _token(usuario.id),
			"otro_token": _token(otro_usuario.id),
			"correo": correo,
			"correo_otro": correo_otro,
		}

	yield datos

	with SessionLocal() as db:
		db.query(Usuario).filter(Usuario.id.in_([datos["id"], datos["otro_id"]])).delete(
			synchronize_session=False
		)
		db.commit()


def _autorizacion(token: str) -> dict[str, str]:
	return {"Authorization": f"Bearer {token}"}


def _usuario_hu09(correo: str):
	with SessionLocal() as db:
		return db.query(Usuario).filter_by(correo=correo).one()


def _codigo_error(respuesta) -> str:
	return respuesta.json()["datos"]["errores"][0]["codigo"]


def test_consulta_autorizada_devuelve_solo_perfil_del_token(perfil_hu09):
	respuesta = client.get(PERFIL, headers=_autorizacion(perfil_hu09["token"]))

	assert respuesta.status_code == 200
	datos = respuesta.json()["datos"]
	assert datos == {
		"id": f"usr_{perfil_hu09['id']:03d}",
		"nombre": "Usuario HU09",
		"correo": perfil_hu09["correo"],
		"telefono": "+573001112233",
		"roles": ["CLIENTE"],
	}
	assert "password" not in respuesta.text
	assert "password_hash" not in respuesta.text


def test_consulta_perfil_no_devuelve_datos_de_otra_identidad(perfil_hu09):
	respuesta = client.get(PERFIL, headers=_autorizacion(perfil_hu09["otro_token"]))

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["correo"] == perfil_hu09["correo_otro"]
	assert respuesta.json()["datos"]["nombre"] == "Otro HU09"


@pytest.mark.parametrize("rol", ["CLIENTE", "PROVEEDOR", "ADMINISTRADOR", "REVISOR"])
def test_get_perfil_disponible_para_cada_rol(perfil_hu09, rol):
	with SessionLocal() as db:
		usuario = db.get(Usuario, perfil_hu09["id"])
		usuario.roles = rol
		db.commit()

	token = _token(perfil_hu09["id"], roles=[rol])
	respuesta = client.get(PERFIL, headers=_autorizacion(token))

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["id"] == f"usr_{perfil_hu09['id']:03d}"
	assert respuesta.json()["datos"]["correo"] == perfil_hu09["correo"]
	assert respuesta.json()["datos"]["roles"] == [rol]


def test_get_perfil_no_expone_identidad_ni_campos_de_terceros(perfil_hu09):
	respuesta = client.get(PERFIL, headers=_autorizacion(perfil_hu09["token"]))

	assert respuesta.status_code == 200
	datos = respuesta.json()["datos"]
	assert datos["id"] == f"usr_{perfil_hu09['id']:03d}"
	assert datos["correo"] == perfil_hu09["correo"]
	assert perfil_hu09["correo_otro"] not in respuesta.text
	assert "Otro HU09" not in respuesta.text
	assert "Otro HU09" not in str(datos)


def test_solicitud_perfil_rechazada_no_modifica_base_de_datos(perfil_hu09):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(perfil_hu09["token"]),
		json={
			"nombre": "Cambio rechazado",
			"telefono": "+573009998877",
			"correo": "rechazado@example.com",
		},
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_NO_EDITABLE"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"
	assert usuario.correo == perfil_hu09["correo"]
	assert usuario.roles == "CLIENTE"


@pytest.mark.parametrize(
	"metodo,cuerpo,estado,exito",
	[
		("get", None, 200, True),
		(
			"put",
			{"nombre": "Cambio rechazado", "telefono": "+573009998877", "correo": "x@example.com"},
			422,
			False,
	),
	],
)
def test_respuestas_perfil_usan_sobre_json_estandar(
	perfil_hu09,
	metodo,
	cuerpo,
	estado,
	exito,
):
	if metodo == "get":
		respuesta = client.get(PERFIL, headers=_autorizacion(perfil_hu09["token"]))
	else:
		respuesta = client.put(
			PERFIL,
			headers=_autorizacion(perfil_hu09["token"]),
			json=cuerpo,
		)

	assert respuesta.status_code == estado
	cuerpo_respuesta = respuesta.json()
	assert set(cuerpo_respuesta) == {"exito", "mensaje", "datos", "fechaHora"}
	assert cuerpo_respuesta["exito"] is exito
	assert isinstance(cuerpo_respuesta["mensaje"], str)
	assert cuerpo_respuesta["datos"] is not None
	assert isinstance(cuerpo_respuesta["fechaHora"], str)


def test_actualizacion_valida_persiste_y_devuelve_perfil_completo(perfil_hu09):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(perfil_hu09["token"]),
		json={"nombre": "Ana Pérez", "telefono": "+573009998877"},
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["mensaje"] == "Perfil actualizado correctamente"
	assert respuesta.json()["datos"]["nombre"] == "Ana Pérez"
	assert respuesta.json()["datos"]["telefono"] == "+573009998877"
	assert respuesta.json()["datos"]["correo"] == perfil_hu09["correo"]
	assert respuesta.json()["datos"]["roles"] == ["CLIENTE"]
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Ana Pérez"
	assert usuario.telefono == "+573009998877"


def test_token_ausente_no_consulta_perfil():
	respuesta = client.get(PERFIL)

	assert respuesta.status_code == 401
	assert respuesta.json()["mensaje"] == "Autenticación requerida o token inválido"
	assert respuesta.json()["datos"] is None


@pytest.mark.parametrize(
	"token",
	[
		"no-es-un-jwt",
		_token(123, dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)),
	],
	ids=["invalido", "vencido"],
)
def test_token_invalido_o_vencido_no_actualiza_perfil(perfil_hu09, token):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(token),
		json={"nombre": "Cambio no autorizado", "telefono": "+573009998877"},
	)

	assert respuesta.status_code == 401
	assert respuesta.json()["mensaje"] == "Autenticación requerida o token inválido"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"


@pytest.mark.parametrize(
	"campo,valor",
	[("roles", ["ADMINISTRADOR"]), ("correo", "otro@example.com")],
)
def test_campos_no_editables_se_rechazan_sin_cambios(perfil_hu09, campo, valor):
	body = {"nombre": "Cambio no autorizado", "telefono": "+573009998877", campo: valor}

	respuesta = client.put(PERFIL, headers=_autorizacion(perfil_hu09["token"]), json=body)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_NO_EDITABLE"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.correo == perfil_hu09["correo"]
	assert usuario.telefono == "+573001112233"
	assert usuario.roles == "CLIENTE"


def test_campo_desconocido_se_rechaza_sin_cambios(perfil_hu09):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(perfil_hu09["token"]),
		json={"nombre": "Cambio parcial", "telefono": "+573009998877", "alias": "ana"},
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_DESCONOCIDO"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"


@pytest.mark.parametrize(
	"body,campo_ausente",
	[
		({"nombre": "Cambio parcial"}, "telefono"),
		({"telefono": "+573009998877"}, "nombre"),
	],
)
def test_campo_obligatorio_ausente_se_rechaza_sin_cambios(
	perfil_hu09,
	body,
	campo_ausente,
):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(perfil_hu09["token"]),
		json=body,
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_OBLIGATORIO"
	assert respuesta.json()["datos"]["errores"][0]["campo"] == campo_ausente
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"


def test_telefono_con_formato_invalido_se_rechaza_sin_cambios(perfil_hu09):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(perfil_hu09["token"]),
		json={"nombre": "Cambio parcial", "telefono": "abc"},
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "FORMATO_INVALIDO"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"


def test_body_con_campo_no_permitido_no_aplica_cambios_parciales(perfil_hu09):
	respuesta = client.put(
		PERFIL,
		headers=_autorizacion(perfil_hu09["token"]),
		json={
			"nombre": "Nombre que no debe guardarse",
			"telefono": "+573009998877",
			"correo": "nuevo@example.com",
		},
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_NO_EDITABLE"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"


def test_json_mal_formado_no_modifica_perfil(perfil_hu09):
	respuesta = client.put(
		PERFIL,
		content=b"{",
		headers={
			**_autorizacion(perfil_hu09["token"]),
			"Content-Type": "application/json",
		},
	)

	assert respuesta.status_code == 400
	assert respuesta.json()["mensaje"] == "Solicitud mal formada"
	usuario = _usuario_hu09(perfil_hu09["correo"])
	assert usuario.nombre == "Usuario HU09"
	assert usuario.telefono == "+573001112233"
