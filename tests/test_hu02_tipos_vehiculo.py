import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.tipos_vehiculo import get_uso
from app.core.config import settings
from app.core.database import Base, get_db
from app.repositories import tipo_vehiculo_repository  # noqa: F401
from main import app


@pytest.fixture()
def client():
    engine_pruebas = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine_pruebas)
    SesionPruebas = sessionmaker(bind=engine_pruebas, autoflush=False, autocommit=False)

    def override_db():
        db = SesionPruebas()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_pruebas)
    engine_pruebas.dispose()


def token(rol="ADMINISTRADOR"):
    firmado = jwt.encode({"sub": "usuario-prueba", "rol": rol}, settings.secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {firmado}"}


ADMIN = token("ADMINISTRADOR")
CLIENTE = token("CLIENTE")
URL = "/api/v1/parametros/tipos-vehiculo"
BODY = {"codigo": "AUTOMOVIL", "nombre": "Automóvil", "categoria": "Liviano", "activo": True}


def test_consultar_requiere_autenticacion(client):
    assert client.get(URL).status_code == 401
    respuesta = client.get(URL, headers=CLIENTE)
    assert respuesta.status_code == 200
    assert respuesta.json()["exito"] is True
    assert respuesta.json()["datos"]["tiposVehiculo"] == []


def test_crear_y_listar_tipo_vehiculo(client):
    respuesta = client.post(URL, json=BODY, headers=ADMIN)
    assert respuesta.status_code == 201
    datos = respuesta.json()["datos"]
    assert datos["tipoVehiculoId"].startswith("tv_")
    assert datos["codigo"] == "AUTOMOVIL"
    listado = client.get(URL, headers=CLIENTE).json()["datos"]["tiposVehiculo"]
    assert len(listado) == 1


def test_normaliza_codigo_y_categoria(client):
    respuesta = client.post(
        URL,
        json={**BODY, "codigo": " camion ", "categoria": " pesado "},
        headers=ADMIN,
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["datos"]["codigo"] == "CAMION"
    assert respuesta.json()["datos"]["categoria"] == "PESADO"


def test_codigo_duplicado_no_distingue_mayusculas(client):
    client.post(URL, json=BODY, headers=ADMIN)
    respuesta = client.post(URL, json={**BODY, "codigo": "automovil"}, headers=ADMIN)
    assert respuesta.status_code == 409
    assert respuesta.json()["exito"] is False


def test_solo_admin_puede_crear_actualizar_y_eliminar(client):
    assert client.post(URL, json=BODY, headers=CLIENTE).status_code == 403
    creado = client.post(URL, json=BODY, headers=ADMIN).json()["datos"]
    assert client.put(
        f'{URL}/{creado["tipoVehiculoId"]}', json=BODY, headers=CLIENTE
    ).status_code == 403
    assert client.delete(
        f'{URL}/{creado["tipoVehiculoId"]}', headers=CLIENTE
    ).status_code == 403


def test_validacion_de_campos_422(client):
    respuesta = client.post(URL, json={**BODY, "codigo": ""}, headers=ADMIN)
    assert respuesta.status_code == 422
    assert respuesta.json()["exito"] is False


def test_json_mal_formado_400(client):
    respuesta = client.post(
        URL,
        content="{no es json",
        headers={**ADMIN, "Content-Type": "application/json"},
    )
    assert respuesta.status_code == 400


def test_actualizar_tipo_existente_y_404(client):
    creado = client.post(URL, json=BODY, headers=ADMIN).json()["datos"]
    tipo_id = creado["tipoVehiculoId"]
    respuesta = client.put(
        f"{URL}/{tipo_id}",
        json={**BODY, "nombre": "Automóvil particular"},
        headers=ADMIN,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["nombre"] == "Automóvil particular"
    assert client.put(f"{URL}/tv_noexiste", json=BODY, headers=ADMIN).status_code == 404


def test_filtro_por_estado_activo(client):
    client.post(URL, json=BODY, headers=ADMIN)
    assert len(client.get(f"{URL}?activo=true", headers=CLIENTE).json()["datos"]["tiposVehiculo"]) == 1
    assert client.get(f"{URL}?activo=false", headers=CLIENTE).json()["datos"]["tiposVehiculo"] == []


def test_no_elimina_si_no_puede_verificar_integracion_mod02(client):
    creado = client.post(URL, json=BODY, headers=ADMIN).json()["datos"]
    respuesta = client.delete(f'{URL}/{creado["tipoVehiculoId"]}', headers=ADMIN)
    assert respuesta.status_code == 503
    assert len(client.get(URL, headers=CLIENTE).json()["datos"]["tiposVehiculo"]) == 1


def test_elimina_si_mod02_confirma_que_no_esta_en_uso(client):
    class SinUso:
        def esta_en_uso(self, tipo_vehiculo_id):
            return False

    app.dependency_overrides[get_uso] = lambda: SinUso()
    creado = client.post(URL, json=BODY, headers=ADMIN).json()["datos"]
    respuesta = client.delete(f'{URL}/{creado["tipoVehiculoId"]}', headers=ADMIN)
    assert respuesta.status_code == 200
    assert client.get(URL, headers=CLIENTE).json()["datos"]["tiposVehiculo"] == []


def test_no_elimina_si_mod02_confirma_que_esta_en_uso(client):
    class EnUso:
        def esta_en_uso(self, tipo_vehiculo_id):
            return True

    app.dependency_overrides[get_uso] = lambda: EnUso()
    creado = client.post(URL, json=BODY, headers=ADMIN).json()["datos"]
    respuesta = client.delete(f'{URL}/{creado["tipoVehiculoId"]}', headers=ADMIN)
    assert respuesta.status_code == 409
    assert len(client.get(URL, headers=CLIENTE).json()["datos"]["tiposVehiculo"]) == 1
