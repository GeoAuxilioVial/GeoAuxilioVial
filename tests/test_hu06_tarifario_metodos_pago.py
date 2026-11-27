import datetime as dt
import uuid

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.tarifario_router import router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.errors import registrar_manejadores
from app.repositories.tarifario_repository import (
    MetodoPagoModel,
    TarifarioModel,
    TarifarioRepository,
)


URL_TARIFARIO = "/api/v1/parametros/tarifario"
URL_METODOS = "/api/v1/parametros/metodos-pago"


def _token(roles: list[str]) -> str:
    return jwt.encode(
        {
            "sub": f"usr_{uuid.uuid4().hex[:8]}",
            "roles": roles,
            "rol": roles[0] if roles else None,
            "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def _headers(roles: list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(roles)}"}


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with factory() as db:
        TarifarioRepository(db).inicializar_catalogos()

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    yield factory

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(test_db):
    app = FastAPI()
    registrar_manejadores(app)
    app.include_router(router)

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _assert_envelope(respuesta, exito: bool):
    datos = respuesta.json()
    assert datos["exito"] is exito
    assert "mensaje" in datos
    assert "datos" in datos
    assert "fechaHora" in datos


def test_consultar_tarifario_con_autenticacion(client):
    respuesta = client.get(
        URL_TARIFARIO,
        headers=_headers(["CLIENTE"]),
    )

    assert respuesta.status_code == 200
    _assert_envelope(respuesta, True)
    assert respuesta.json()["datos"]["tarifarioVersion"] == "v1"
    assert respuesta.json()["datos"]["moneda"] == "COP"


def test_consultar_tarifario_sin_token(client):
    respuesta = client.get(URL_TARIFARIO)

    assert respuesta.status_code == 401
    _assert_envelope(respuesta, False)


def test_actualizar_tarifario_como_administrador(client, test_db):
    respuesta = client.put(
        URL_TARIFARIO,
        json={
            "moneda": "COP",
            "tarifaBase": 75000,
            "valorPorKm": 3000,
            "recargos": [
                {"concepto": "RECARGO_NOCTURNO", "valor": 15000}
            ],
        },
        headers=_headers(["ADMINISTRADOR"]),
    )

    assert respuesta.status_code == 200
    _assert_envelope(respuesta, True)
    assert respuesta.json()["datos"]["tarifarioVersion"] == "v2"
    assert respuesta.json()["datos"]["tarifaBase"] == 75000.0

    with test_db() as db:
        versiones = db.scalars(
            select(TarifarioModel).order_by(TarifarioModel.version_num)
        ).all()

        assert len(versiones) == 2
        assert versiones[0].vigente is False
        assert versiones[1].vigente is True


def test_actualizar_tarifario_sin_permiso_admin(client):
    respuesta = client.put(
        URL_TARIFARIO,
        json={
            "moneda": "COP",
            "tarifaBase": 75000,
            "valorPorKm": 3000,
            "recargos": [],
        },
        headers=_headers(["CLIENTE"]),
    )

    assert respuesta.status_code == 403
    _assert_envelope(respuesta, False)


def test_tarifario_rechaza_importes_negativos(client):
    respuesta = client.put(
        URL_TARIFARIO,
        json={
            "moneda": "COP",
            "tarifaBase": -1000,
            "valorPorKm": 3000,
            "recargos": [],
        },
        headers=_headers(["ADMINISTRADOR"]),
    )

    assert respuesta.status_code == 422
    _assert_envelope(respuesta, False)


def test_tarifario_rechaza_recargos_duplicados(client):
    respuesta = client.put(
        URL_TARIFARIO,
        json={
            "moneda": "COP",
            "tarifaBase": 60000,
            "valorPorKm": 2300,
            "recargos": [
                {"concepto": "RECARGO_NOCTURNO", "valor": 10000},
                {"concepto": "RECARGO_NOCTURNO", "valor": 15000},
            ],
        },
        headers=_headers(["ADMINISTRADOR"]),
    )

    assert respuesta.status_code == 422
    _assert_envelope(respuesta, False)


def test_tarifario_no_acepta_datos_de_tarjeta(client):
    respuesta = client.put(
        URL_TARIFARIO,
        json={
            "moneda": "COP",
            "tarifaBase": 60000,
            "valorPorKm": 2300,
            "recargos": [],
            "numeroTarjeta": "4111111111111111",
        },
        headers=_headers(["ADMINISTRADOR"]),
    )

    assert respuesta.status_code == 422
    _assert_envelope(respuesta, False)


def test_listar_metodos_pago(client):
    respuesta = client.get(
        URL_METODOS,
        headers=_headers(["CLIENTE"]),
    )

    assert respuesta.status_code == 200
    _assert_envelope(respuesta, True)

    metodos = respuesta.json()["datos"]["metodosPago"]
    assert len(metodos) >= 1
    assert all("metodoPagoId" in metodo for metodo in metodos)


def test_actualizar_metodo_pago(client, test_db):
    consulta = client.get(
        URL_METODOS,
        headers=_headers(["ADMINISTRADOR"]),
    )
    metodo_id = consulta.json()["datos"]["metodosPago"][0]["metodoPagoId"]

    respuesta = client.put(
        f"{URL_METODOS}/{metodo_id}",
        json={"habilitado": False},
        headers=_headers(["ADMINISTRADOR"]),
    )

    assert respuesta.status_code == 200
    _assert_envelope(respuesta, True)
    assert respuesta.json()["datos"]["habilitado"] is False

    with test_db() as db:
        metodo = db.get(MetodoPagoModel, metodo_id)
        assert metodo is not None
        assert metodo.habilitado is False


def test_actualizar_metodo_pago_inexistente(client):
    respuesta = client.put(
        f"{URL_METODOS}/mp_inexistente",
        json={"habilitado": False},
        headers=_headers(["ADMINISTRADOR"]),
    )

    assert respuesta.status_code == 404
    _assert_envelope(respuesta, False)


def test_actualizar_metodo_pago_sin_permiso_admin(client):
    consulta = client.get(
        URL_METODOS,
        headers=_headers(["CLIENTE"]),
    )
    metodo_id = consulta.json()["datos"]["metodosPago"][0]["metodoPagoId"]

    respuesta = client.put(
        f"{URL_METODOS}/{metodo_id}",
        json={"habilitado": False},
        headers=_headers(["CLIENTE"]),
    )

    assert respuesta.status_code == 403
    _assert_envelope(respuesta, False)
