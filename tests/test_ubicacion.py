import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.domain.proveedor_domain import Proveedor
from app.domain.usuario_domain import Usuario
from app.repositories import proveedor_repository
from main import app


client = TestClient(app, raise_server_exceptions=False)
UBICACION = "/api/v1/proveedores/me/ubicacion"


def _token(usuario_id: int, roles: list[str]) -> str:
	return jwt.encode(
		{
			"sub": f"usr_{usuario_id:03d}",
			"roles": roles,
			"rol": roles[0],
		},
		settings.secret_key,
		algorithm="HS256",
	)


def _crear_usuario_y_proveedor(
	correo: str,
	estado: str = "HABILITADO",
	roles: list[str] | None = None,
):
	with SessionLocal() as db:
		usuario = Usuario(
			nombre="Proveedor HU17",
			correo=correo,
			password_hash="no-se-expone",
			roles=",".join(roles or ["PROVEEDOR"]),
		)
		db.add(usuario)
		db.commit()
		db.refresh(usuario)
		proveedor = Proveedor(
			usuario_id=usuario.id,
			estado_habilitacion=estado,
		)
		db.add(proveedor)
		db.commit()
		db.refresh(proveedor)
		return usuario.id, proveedor.id


@pytest.fixture(autouse=True)
def limpiar_datos_hu17():
	with SessionLocal() as db:
		for usuario in db.query(Usuario).filter(Usuario.correo.like("hu17.%")).all():
			db.query(Proveedor).filter(Proveedor.usuario_id == usuario.id).delete()
			db.delete(usuario)
		db.commit()
	yield
	with SessionLocal() as db:
		for usuario in db.query(Usuario).filter(Usuario.correo.like("hu17.%")).all():
			db.query(Proveedor).filter(Proveedor.usuario_id == usuario.id).delete()
			db.delete(usuario)
		db.commit()


def test_coordenadas_validas():
	usuario_id, _ = _crear_usuario_y_proveedor("hu17.validas@example.com")
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227, "precisionMetros": 20},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 200
	assert r.json()["exito"] is True
	assert r.json()["mensaje"] == "Ubicación actualizada"
	assert r.json()["datos"]["latitud"] == 7.1193
	assert r.json()["datos"]["longitud"] == -73.1227
	assert r.json()["datos"]["precisionMetros"] == 20
	assert r.json()["datos"]["actualizadaEn"]


def test_latitud_fuera_de_rango_conserva_ubicacion_previa():
	usuario_id, proveedor_id = _crear_usuario_y_proveedor("hu17.latitud@example.com")
	with SessionLocal() as db:
		db_proveedor = db.get(Proveedor, proveedor_id)
		db_proveedor.latitud = 7.1
		db_proveedor.longitud = -73.1
		db.commit()
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 95, "longitud": -73.1227},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "FUERA_DE_RANGO"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud == 7.1
		assert guardada.longitud == -73.1


def test_longitud_fuera_de_rango_conserva_ubicacion_previa():
	usuario_id, proveedor_id = _crear_usuario_y_proveedor("hu17.longitud@example.com")
	with SessionLocal() as db:
		db_proveedor = db.get(Proveedor, proveedor_id)
		db_proveedor.latitud = 7.1
		db_proveedor.longitud = -73.1
		db.commit()
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": 200},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "FUERA_DE_RANGO"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud == 7.1


def test_coordenada_ausente():
	usuario_id, _ = _crear_usuario_y_proveedor("hu17.ausente@example.com")
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "CAMPO_OBLIGATORIO"
	assert r.json()["datos"]["errores"][0]["campo"] == "longitud"


def test_precision_negativa_conserva_ubicacion_previa():
	usuario_id, proveedor_id = _crear_usuario_y_proveedor("hu17.precision@example.com")
	with SessionLocal() as db:
		db_proveedor = db.get(Proveedor, proveedor_id)
		db_proveedor.latitud = 7.1
		db_proveedor.longitud = -73.1
		db.commit()
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227, "precisionMetros": -5},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 422
	assert r.json()["datos"]["errores"][0]["codigo"] == "FUERA_DE_RANGO"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud == 7.1
		assert guardada.longitud == -73.1


def test_json_mal_formado():
	usuario_id, proveedor_id = _crear_usuario_y_proveedor("hu17.json@example.com")
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		content=b"{",
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
	)
	assert r.status_code == 400
	assert r.json()["mensaje"] == "Solicitud mal formada"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud is None


def test_usuario_cliente_sin_rol_proveedor():
	usuario_id, proveedor_id = _crear_usuario_y_proveedor(
		"hu17.cliente@example.com",
		roles=["CLIENTE"],
	)
	token = _token(usuario_id, ["CLIENTE"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 403
	assert r.json()["mensaje"] == "No tiene permisos para realizar esta operación"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud is None


@pytest.mark.parametrize("estado", ["PENDIENTE", "SUSPENDIDO"])
def test_proveedor_no_habilitado(estado):
	usuario_id, proveedor_id = _crear_usuario_y_proveedor(
		f"hu17.nohabilitado-{estado.lower()}@example.com",
		estado=estado,
	)
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 409
	assert r.json()["datos"]["codigo"] == "PROVEEDOR_NO_HABILITADO"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud is None


def test_token_ausente():
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227},
	)
	assert r.status_code == 401
	assert r.json()["mensaje"] == "Autenticación requerida o token inválido"


def test_timestamp_del_cliente_se_ignora():
	usuario_id, _ = _crear_usuario_y_proveedor("hu17.timestamp@example.com")
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={
			"latitud": 7.1193,
			"longitud": -73.1227,
			"actualizadaEn": "2000-01-01T00:00:00-05:00",
		},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 200
	assert r.json()["datos"]["actualizadaEn"].startswith("20")
	assert r.json()["datos"]["actualizadaEn"] != "2000-01-01T00:00:00-05:00"


def test_ubicacion_persistida_para_busqueda_posterior():
	usuario_id, proveedor_id = _crear_usuario_y_proveedor("hu17.busqueda@example.com")
	token = _token(usuario_id, ["PROVEEDOR"])
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227, "precisionMetros": 15},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 200
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.estado_habilitacion == "HABILITADO"
		assert guardada.latitud == 7.1193
		assert guardada.longitud == -73.1227
		assert guardada.actualizada_en is not None


def test_error_de_persistencia_no_confirma_cambio(monkeypatch):
	usuario_id, proveedor_id = _crear_usuario_y_proveedor("hu17.persistencia@example.com")
	token = _token(usuario_id, ["PROVEEDOR"])
	monkeypatch.setattr(app, "debug", False)
	app.middleware_stack = None

	def fallar_guardado(db, proveedor):
		raise RuntimeError("Falla controlada de persistencia")

	monkeypatch.setattr(proveedor_repository, "guardar", fallar_guardado)
	r = client.put(
		UBICACION,
		json={"latitud": 7.1193, "longitud": -73.1227},
		headers={"Authorization": f"Bearer {token}"},
	)
	assert r.status_code == 500
	assert r.json()["mensaje"] == "Error interno controlado"
	with SessionLocal() as db:
		guardada = db.get(Proveedor, proveedor_id)
		assert guardada.latitud is None
