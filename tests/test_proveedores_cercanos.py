import datetime as dt
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.errors import ZONA
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import DatosProveedor, ProveedorZonaCobertura
from app.domain.zonas_cobertura_domain import ZonaCobertura
from app.repositories import proveedor_cercano_repository
from main import app

BUSQUEDA = "/api/v1/proveedores/cercanos"
LATITUD = 7.1193
LONGITUD = -73.1227


def _token(rol: str) -> str:
	return jwt.encode(
		{
			"sub": "usr_900",
			"roles": [rol],
			"rol": rol,
			"exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
		},
		settings.secret_key,
		algorithm="HS256",
	)


def _headers(rol: str = "CLIENTE") -> dict[str, str]:
	return {"Authorization": f"Bearer {_token(rol)}"}


def _params(**cambios) -> dict:
	return {
		"latitud": LATITUD,
		"longitud": LONGITUD,
		"tipoServicio": "GRUA",
		"radioKm": 15,
		**cambios,
	}


@pytest.fixture
def busqueda_context():
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


def _crear_zona(
	contexto,
	latitud: float = LATITUD,
	longitud: float = LONGITUD,
	radio_km: float = 10,
	activa: bool = True,
) -> int:
	with contexto["db"]() as db:
		zona = ZonaCobertura(
			nombre=f"Zona-{uuid.uuid4().hex}",
			latitud_centro=latitud,
			longitud_centro=longitud,
			radio_km=radio_km,
			activa=activa,
		)
		db.add(zona)
		db.commit()
		db.refresh(zona)
		return zona.id


def _crear_proveedor(
	contexto,
	zona_id: int,
	latitud: float = LATITUD,
	longitud: float = LONGITUD,
	tipo: str = "GRUA",
	estado_habilitacion: str = "HABILITADO",
	estado_operativo: str = "DISPONIBLE",
	minutos_antiguedad: int = 0,
) -> int:
	with contexto["db"]() as db:
		proveedor = Proveedor(
			usuario_id=uuid.uuid4().int % 2_000_000_000,
			estado_habilitacion=estado_habilitacion,
			estado_operativo=estado_operativo,
			latitud=latitud,
			longitud=longitud,
			actualizada_en=(
				dt.datetime.now(ZONA) - dt.timedelta(minutes=minutos_antiguedad)
			),
		)
		db.add(proveedor)
		db.flush()
		db.add(
			DatosProveedor(
				proveedor_id=proveedor.id,
				nombre_comercial=f"Proveedor-{proveedor.id}",
				tipo_proveedor=tipo,
			)
		)
		db.add(
			ProveedorZonaCobertura(
				proveedor_id=proveedor.id,
				zona_id=zona_id,
			)
		)
		db.commit()
		return proveedor.id


def _buscar(contexto, params: dict | None = None, rol: str = "CLIENTE"):
	return contexto["client"].get(
		BUSQUEDA,
		params=params or _params(),
		headers=_headers(rol),
	)


def _codigo_error(respuesta) -> str:
	return respuesta.json()["datos"]["errores"][0]["codigo"]


@pytest.mark.parametrize("rol", ["CLIENTE", "ADMINISTRADOR"])
def test_candidatos_disponibles_ordenados_y_con_datos_minimos(busqueda_context, rol):
	zona_id = _crear_zona(busqueda_context)
	lejos = _crear_proveedor(
		busqueda_context, zona_id, latitud=7.1493
	)
	cerca = _crear_proveedor(
		busqueda_context, zona_id, latitud=7.1293
	)

	respuesta = _buscar(busqueda_context, rol=rol)

	assert respuesta.status_code == 200
	proveedores = respuesta.json()["datos"]["proveedores"]
	assert [p["id"] for p in proveedores] == [
		f"prov_{cerca:03d}",
		f"prov_{lejos:03d}",
	]
	assert [p["distanciaKm"] for p in proveedores] == sorted(
		p["distanciaKm"] for p in proveedores
	)
	for proveedor in proveedores:
		assert set(proveedor) == {
			"id",
			"nombreComercial",
			"distanciaKm",
			"estado",
			"calificacionPromedio",
		}
		assert proveedor["estado"] == "DISPONIBLE"
		assert proveedor["calificacionPromedio"] is None


def test_busqueda_sin_candidatos_devuelve_lista_vacia(busqueda_context):
	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


@pytest.mark.parametrize(
	"params,campo",
	[
		(_params(latitud=120), "latitud"),
		(_params(longitud=181), "longitud"),
	],
)
def test_coordenadas_fuera_de_rango_no_buscan(
	busqueda_context, monkeypatch, params, campo
):
	def fallar_busqueda(db, tipo):
		pytest.fail("La consulta no debe ejecutarse con coordenadas inválidas")

	monkeypatch.setattr(
		proveedor_cercano_repository, "listar_candidatos", fallar_busqueda
	)
	respuesta = _buscar(busqueda_context, params=params)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "FUERA_DE_RANGO"
	assert respuesta.json()["datos"]["errores"][0]["campo"] == campo
	assert set(respuesta.json()) == {"exito", "mensaje", "datos", "fechaHora"}


@pytest.mark.parametrize(
	"radio",
	[0, settings.radio_busqueda_max_km + 1],
)
def test_radio_invalido_no_busca(busqueda_context, radio):
	respuesta = _buscar(busqueda_context, params=_params(radioKm=radio))

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "FUERA_DE_RANGO"


def test_tipo_servicio_fuera_de_catalogo_no_busca(busqueda_context):
	respuesta = _buscar(
		busqueda_context, params=_params(tipoServicio="AVION")
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "VALOR_FUERA_DE_CATALOGO"


def test_parametro_obligatorio_ausente(busqueda_context):
	params = _params()
	del params["longitud"]

	respuesta = _buscar(busqueda_context, params=params)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_OBLIGATORIO"
	assert respuesta.json()["datos"]["errores"][0]["campo"] == "longitud"


def test_proveedor_fuera_de_cobertura_no_aparece(busqueda_context):
	zona_id = _crear_zona(
		busqueda_context,
		latitud=7.5,
		longitud=LONGITUD,
		radio_km=1,
	)
	_crear_proveedor(busqueda_context, zona_id)

	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert set(respuesta.json()) == {"exito", "mensaje", "datos", "fechaHora"}
	assert respuesta.json()["datos"]["proveedores"] == []


def test_proveedor_fuera_del_radio_consultado_no_aparece(busqueda_context):
	zona_id = _crear_zona(busqueda_context, radio_km=15)
	_crear_proveedor(
		busqueda_context, zona_id, latitud=LATITUD + 0.1
	)

	respuesta = _buscar(busqueda_context, params=_params(radioKm=5))

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


def test_busqueda_usa_centro_radio_y_estado_actual_de_zona_hu03(busqueda_context):
	zona_id = _crear_zona(
		busqueda_context,
		latitud=7.0,
		longitud=LONGITUD,
		radio_km=1,
	)
	_crear_proveedor(busqueda_context, zona_id)

	inicial = _buscar(busqueda_context)
	assert inicial.json()["datos"]["proveedores"] == []

	with busqueda_context["db"]() as db:
		zona = db.get(ZonaCobertura, zona_id)
		zona.latitud_centro = LATITUD
		zona.longitud_centro = LONGITUD
		zona.radio_km = 5
		db.commit()

	actualizada = _buscar(busqueda_context)
	assert actualizada.status_code == 200
	assert len(actualizada.json()["datos"]["proveedores"]) == 1


def test_zona_inactiva_no_aporta_cobertura(busqueda_context):
	zona_id = _crear_zona(busqueda_context, activa=False)
	_crear_proveedor(busqueda_context, zona_id)

	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


def test_proveedor_de_otro_tipo_no_aparece(busqueda_context):
	zona_id = _crear_zona(busqueda_context)
	_crear_proveedor(busqueda_context, zona_id, tipo="GRUA")

	respuesta = _buscar(
		busqueda_context, params=_params(tipoServicio="MECANICO")
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


def test_ubicacion_desactualizada_no_aparece(busqueda_context):
	zona_id = _crear_zona(busqueda_context)
	_crear_proveedor(
		busqueda_context,
		zona_id,
		minutos_antiguedad=settings.ubicacion_frescura_minutos + 1,
	)

	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


def test_proveedor_no_disponible_no_aparece_hu15(busqueda_context):
	zona_id = _crear_zona(busqueda_context)
	_crear_proveedor(
		busqueda_context, zona_id, estado_operativo="NO_DISPONIBLE"
	)

	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


def test_proveedor_suspendido_por_documentos_vencidos_no_aparece_hu16(
	busqueda_context,
):
	zona_id = _crear_zona(busqueda_context)
	_crear_proveedor(
		busqueda_context,
		zona_id,
		estado_habilitacion="SUSPENDIDO",
		estado_operativo="NO_DISPONIBLE",
	)

	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"] == []


def test_proveedor_sin_calificaciones_devuelve_null(busqueda_context):
	zona_id = _crear_zona(busqueda_context)
	_crear_proveedor(busqueda_context, zona_id)

	respuesta = _buscar(busqueda_context)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedores"][0]["calificacionPromedio"] is None


def test_rol_revisor_no_ejecuta_busqueda(busqueda_context, monkeypatch):
	def fallar_busqueda(db, tipo):
		pytest.fail("No debe ejecutar búsqueda para un rol no autorizado")

	monkeypatch.setattr(
		proveedor_cercano_repository, "listar_candidatos", fallar_busqueda
	)
	respuesta = _buscar(busqueda_context, rol="REVISOR")

	assert respuesta.status_code == 403


def test_token_ausente_no_ejecuta_busqueda(busqueda_context, monkeypatch):
	def fallar_busqueda(db, tipo):
		pytest.fail("No debe ejecutar búsqueda sin autenticación")

	monkeypatch.setattr(
		proveedor_cercano_repository, "listar_candidatos", fallar_busqueda
	)
	respuesta = busqueda_context["client"].get(BUSQUEDA, params=_params())

	assert respuesta.status_code == 401
