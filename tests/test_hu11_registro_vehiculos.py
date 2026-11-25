
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.vehiculos import router as vehiculos_router
from app.core.config import settings
from app.core.database import Base, get_db
from app.domain.usuario_domain import Usuario
from app.domain.vehiculo import Vehiculo
from app.repositories import tipo_vehiculo_repository  # noqa: F401
from app.repositories.tipo_vehiculo_repository import TipoVehiculoRepository
from main import app


URL = "/api/v1/vehiculos"

# Registrar el router para las pruebas sin modificar main.py.
app.include_router(vehiculos_router)


@pytest.fixture()
def contexto():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SesionPruebas = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    overrides_anteriores = app.dependency_overrides.copy()

    def override_db():
        db = SesionPruebas()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db

    try:
        with SesionPruebas() as db:
            usuario = Usuario(
                nombre="Cliente HU11",
                correo="cliente.hu11@example.com",
                password_hash="hash-prueba",
                roles="CLIENTE",
            )

            otro_usuario = Usuario(
                nombre="Otro cliente HU11",
                correo="otro.hu11@example.com",
                password_hash="hash-prueba",
                roles="CLIENTE",
            )

            db.add_all([usuario, otro_usuario])
            db.commit()

            db.refresh(usuario)
            db.refresh(otro_usuario)

            tipo = TipoVehiculoRepository(db).crear(
                codigo="AUTOMOVIL",
                nombre="Automóvil",
                categoria="LIVIANO",
                activo=True,
            )

            datos = {
                "tipo_id": tipo.id,
                "token": jwt.encode(
                    {
                        "sub": usuario.usuario_id,
                        "roles": ["CLIENTE"],
                        "rol": "CLIENTE",
                    },
                    settings.secret_key,
                    algorithm="HS256",
                ),
                "otro_token": jwt.encode(
                    {
                        "sub": otro_usuario.usuario_id,
                        "roles": ["CLIENTE"],
                        "rol": "CLIENTE",
                    },
                    settings.secret_key,
                    algorithm="HS256",
                ),
            }

        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            yield {"client": client, **datos}

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides_anteriores)

        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def autorizacion(token):
    return {"Authorization": f"Bearer {token}"}


def body(tipo_id, **cambios):
    datos = {
        "placa": "ABC123",
        "marca": "Renault",
        "modelo": "Logan",
        "anio": 2021,
        "tipoVehiculoId": tipo_id,
        "kilometraje": 45000,
    }

    datos.update(cambios)
    return datos


def test_registrar_vehiculo_valido(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"]),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 201

    datos = respuesta.json()["datos"]

    assert datos["vehiculoId"].startswith("veh_")
    assert datos["placa"] == "ABC123"
    assert datos["tipoVehiculoId"] == contexto["tipo_id"]


def test_normaliza_placa_antes_de_guardar(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"], placa=" abc-123 "),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["datos"]["placa"] == "ABC123"


def test_no_registra_placa_duplicada(contexto):
    cliente = contexto["client"]
    headers = autorizacion(contexto["token"])

    primera = cliente.post(
        URL,
        json=body(contexto["tipo_id"]),
        headers=headers,
    )

    segunda = cliente.post(
        URL,
        json=body(contexto["tipo_id"], placa="abc-123"),
        headers=headers,
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409


def test_rechaza_placa_con_formato_invalido(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"], placa="AB123"),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 422


def test_rechaza_propietario_enviado_en_body(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"], propietarioId="usr_999"),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 422


def test_requiere_autenticacion(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"]),
    )

    assert respuesta.status_code == 401


def test_rechaza_tipo_de_vehiculo_inexistente(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body("tv_noexiste"),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 404


def test_actualiza_vehiculo_del_propietario(contexto):
    cliente = contexto["client"]
    headers = autorizacion(contexto["token"])

    creado = cliente.post(
        URL,
        json=body(contexto["tipo_id"]),
        headers=headers,
    )

    vehiculo_id = creado.json()["datos"]["vehiculoId"]

    respuesta = cliente.put(
        f"{URL}/{vehiculo_id}",
        json=body(contexto["tipo_id"], kilometraje=50000),
        headers=headers,
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["kilometraje"] == 50000


def test_no_actualiza_vehiculo_de_otro_propietario(contexto):
    cliente = contexto["client"]

    creado = cliente.post(
        URL,
        json=body(contexto["tipo_id"]),
        headers=autorizacion(contexto["token"]),
    )

    vehiculo_id = creado.json()["datos"]["vehiculoId"]

    respuesta = cliente.put(
        f"{URL}/{vehiculo_id}",
        json=body(contexto["tipo_id"], kilometraje=90000),
        headers=autorizacion(contexto["otro_token"]),
    )

    assert respuesta.status_code == 404


def test_actualizar_vehiculo_inexistente_devuelve_404(contexto):
    respuesta = contexto["client"].put(
        f"{URL}/veh_noexiste",
        json=body(contexto["tipo_id"]),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 404


def test_rechaza_kilometraje_negativo(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"], kilometraje=-1),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 422


def test_rechaza_anio_futuro_fuera_del_rango(contexto):
    respuesta = contexto["client"].post(
        URL,
        json=body(contexto["tipo_id"], anio=9999),
        headers=autorizacion(contexto["token"]),
    )

    assert respuesta.status_code == 422
