import datetime as dt
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.domain.proveedor_domain import Proveedor
from app.domain.usuario_domain import Usuario
from app.repositories import proveedor_hu15_repository
from main import app
from migrate_hu15_provider_column import migrar_columna_hu15

DISPONIBILIDAD = "/api/v1/proveedores/me/disponibilidad"


def _token(usuario_id: int, roles: list[str]) -> str:
	return jwt.encode(
		{
			"sub": f"usr_{usuario_id:03d}",
			"roles": roles,
			"rol": roles[0],
			"exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
		},
		settings.secret_key,
		algorithm="HS256",
	)


def _headers(usuario_id: int, roles: list[str]) -> dict[str, str]:
	return {"Authorization": f"Bearer {_token(usuario_id, roles)}"}


@pytest.fixture
def disponibilidad_context():
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	Base.metadata.create_all(bind=engine)
	factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

	def override_get_db():
		db = factory()
		try:
			yield db
		finally:
			db.close()

	app.dependency_overrides[get_db] = override_get_db
	try:
		with TestClient(app, raise_server_exceptions=False) as client:
			yield {"db": factory, "client": client}
	finally:
		app.dependency_overrides.pop(get_db, None)
		Base.metadata.drop_all(bind=engine)
		engine.dispose()


def _crear_proveedor(
	contexto,
	estado_habilitacion: str = "HABILITADO",
	estado_operativo: str = "NO_DISPONIBLE",
	roles: str = "PROVEEDOR",
) -> tuple[int, int]:
	with contexto["db"]() as db:
		usuario = Usuario(
			nombre="Proveedor HU15",
			correo=f"hu15.{uuid.uuid4().hex}@example.com",
			password_hash="hash-no-utilizado",
			roles=roles,
		)
		db.add(usuario)
		db.flush()
		proveedor = Proveedor(
			usuario_id=usuario.id,
			estado_habilitacion=estado_habilitacion,
			estado_operativo=estado_operativo,
		)
		db.add(proveedor)
		db.commit()
		return usuario.id, proveedor.id


def _actualizar(contexto, usuario_id: int, estado: str):
	return contexto["client"].patch(
		DISPONIBILIDAD,
		json={"estado": estado},
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)


def _proveedor_guardado(contexto, proveedor_id: int) -> Proveedor:
	with contexto["db"]() as db:
		return db.get(Proveedor, proveedor_id)


def test_activacion_valida_persiste_estado_y_fecha(disponibilidad_context):
	usuario_id, proveedor_id = _crear_proveedor(disponibilidad_context)

	respuesta = _actualizar(disponibilidad_context, usuario_id, "DISPONIBLE")

	assert respuesta.status_code == 200
	cuerpo = respuesta.json()
	assert cuerpo["mensaje"] == "Disponibilidad actualizada"
	assert cuerpo["datos"]["proveedorId"] == f"prov_{proveedor_id:03d}"
	assert cuerpo["datos"]["estado"] == "DISPONIBLE"
	fecha = dt.datetime.fromisoformat(cuerpo["datos"]["actualizadoEn"])
	assert fecha.utcoffset() == dt.timedelta(hours=-5)
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is not None
	assert proveedor.actualizada_en is None


def test_desactivacion_valida(disponibilidad_context):
	usuario_id, proveedor_id = _crear_proveedor(
		disponibilidad_context, estado_operativo="DISPONIBLE"
	)

	respuesta = _actualizar(disponibilidad_context, usuario_id, "NO_DISPONIBLE")

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["estado"] == "NO_DISPONIBLE"
	assert _proveedor_guardado(disponibilidad_context, proveedor_id).estado_operativo == "NO_DISPONIBLE"


def test_desactivacion_permitida_para_proveedor_suspendido(disponibilidad_context):
	usuario_id, proveedor_id = _crear_proveedor(
		disponibilidad_context,
		estado_habilitacion="SUSPENDIDO",
		estado_operativo="DISPONIBLE",
	)

	respuesta = _actualizar(disponibilidad_context, usuario_id, "NO_DISPONIBLE")

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["estado"] == "NO_DISPONIBLE"
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_habilitacion == "SUSPENDIDO"


@pytest.mark.parametrize("estado_habilitacion", ["SUSPENDIDO", "PENDIENTE"])
def test_no_puede_activarse_sin_habilitacion(disponibilidad_context, estado_habilitacion):
	usuario_id, proveedor_id = _crear_proveedor(
		disponibilidad_context,
		estado_habilitacion=estado_habilitacion,
	)

	respuesta = _actualizar(disponibilidad_context, usuario_id, "DISPONIBLE")

	assert respuesta.status_code == 409
	assert respuesta.json()["datos"] == {"codigo": "PROVEEDOR_NO_HABILITADO"}
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is None


def test_estado_fuera_de_catalogo_se_rechaza_sin_cambios(disponibilidad_context):
	usuario_id, proveedor_id = _crear_proveedor(disponibilidad_context)

	respuesta = disponibilidad_context["client"].patch(
		DISPONIBILIDAD,
		json={"estado": "TAL_VEZ"},
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)

	assert respuesta.status_code == 422
	assert respuesta.json()["datos"]["errores"][0]["codigo"] == "VALOR_FUERA_DE_CATALOGO"
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is None


def test_campo_estado_ausente_se_rechaza_sin_cambios(disponibilidad_context):
	usuario_id, proveedor_id = _crear_proveedor(disponibilidad_context)

	respuesta = disponibilidad_context["client"].patch(
		DISPONIBILIDAD,
		json={},
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)

	assert respuesta.status_code == 422
	assert respuesta.json()["datos"]["errores"][0]["codigo"] == "CAMPO_OBLIGATORIO"
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is None


def test_usuario_no_proveedor_no_modifica_disponibilidad(disponibilidad_context):
	usuario_id, proveedor_id = _crear_proveedor(
		disponibilidad_context, roles="CLIENTE"
	)

	respuesta = disponibilidad_context["client"].patch(
		DISPONIBILIDAD,
		json={"estado": "DISPONIBLE"},
		headers=_headers(usuario_id, ["CLIENTE"]),
	)

	assert respuesta.status_code == 403
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is None


def test_token_ausente_no_modifica_disponibilidad(disponibilidad_context):
	_, proveedor_id = _crear_proveedor(disponibilidad_context)

	respuesta = disponibilidad_context["client"].patch(
		DISPONIBILIDAD, json={"estado": "DISPONIBLE"}
	)

	assert respuesta.status_code == 401
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is None


def test_error_de_persistencia_no_confirma_cambio(
	disponibilidad_context, monkeypatch
):
	usuario_id, proveedor_id = _crear_proveedor(disponibilidad_context)
	monkeypatch.setattr(app, "debug", False)
	monkeypatch.setattr(app, "middleware_stack", None)

	def fallar_guardado(db, proveedor):
		raise RuntimeError("Falla controlada de persistencia")

	monkeypatch.setattr(proveedor_hu15_repository, "guardar", fallar_guardado)
	respuesta = _actualizar(disponibilidad_context, usuario_id, "DISPONIBLE")

	assert respuesta.status_code == 500
	assert respuesta.json()["mensaje"] == "Error interno controlado"
	proveedor = _proveedor_guardado(disponibilidad_context, proveedor_id)
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.estado_operativo_actualizado_en is None


def test_migracion_hu15_agrega_columna_idempotente_y_conserva_datos():
	engine = create_engine("sqlite://")
	try:
		with engine.begin() as conexion:
			conexion.execute(
				text(
					"CREATE TABLE proveedores ("
					"id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL)"
				)
			)
			conexion.execute(
				text("INSERT INTO proveedores (id, usuario_id) VALUES (1, 23)")
			)

		assert migrar_columna_hu15(engine) is True
		assert migrar_columna_hu15(engine) is False
		with engine.connect() as conexion:
			proveedor = conexion.execute(
				text("SELECT * FROM proveedores WHERE id=1")
			).mappings().one()

		assert proveedor["usuario_id"] == 23
		assert proveedor["estado_operativo_actualizado_en"] is None
	finally:
		engine.dispose()


def test_migracion_hu15_falla_si_no_existe_tabla_proveedores():
	engine = create_engine("sqlite://")
	try:
		with pytest.raises(RuntimeError, match="No existe la tabla proveedores"):
			migrar_columna_hu15(engine)
	finally:
		engine.dispose()
