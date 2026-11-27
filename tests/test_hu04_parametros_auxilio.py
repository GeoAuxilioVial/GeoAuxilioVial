import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.parametros_auxilio import get_uso_tipo_averia
from app.core.config import settings
from app.core.database import Base, get_db
from app.repositories.parametros_auxilio_repository import ReglaAuxilioModel
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
    with SesionPruebas() as db:
        from app.repositories.parametros_auxilio_repository import ParametrosAuxilioRepository
        ParametrosAuxilioRepository(db).inicializar_catalogos()
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
TIPOS = "/api/v1/parametros/tipos-averia"
REGLAS = "/api/v1/parametros/reglas-auxilio"
BODY = {"codigo": "FUGA_ACEITE", "nombre": "Fuga de aceite", "activo": True}


def test_consultar_catalogos_requiere_autenticacion(client):
    assert client.get(TIPOS).status_code == 401
    assert client.get(REGLAS).status_code == 401
    assert client.get(TIPOS, headers=CLIENTE).status_code == 200
    assert client.get(REGLAS, headers=CLIENTE).status_code == 200


def test_inicializa_los_cinco_tipos_de_averia_del_alcance(client):
    respuesta = client.get(TIPOS, headers=CLIENTE)
    assert respuesta.status_code == 200
    codigos = {t["codigo"] for t in respuesta.json()["datos"]["tiposAveria"]}
    assert codigos == {
        "PONCHADURA", "DESCARGA_BATERIA", "FALTA_COMBUSTIBLE", "RECALENTAMIENTO", "REMOLQUE"
    }


def test_crear_tipo_averia_y_normalizar_codigo(client):
    respuesta = client.post(TIPOS, json={**BODY, "codigo": " fuga_aceite "}, headers=ADMIN)
    assert respuesta.status_code == 201
    assert respuesta.json()["datos"]["codigo"] == "FUGA_ACEITE"


def test_no_permite_codigo_duplicado(client):
    client.post(TIPOS, json=BODY, headers=ADMIN)
    respuesta = client.post(TIPOS, json=BODY, headers=ADMIN)
    assert respuesta.status_code == 409


def test_solo_admin_puede_crear_actualizar_y_eliminar_tipo(client):
    assert client.post(TIPOS, json=BODY, headers=CLIENTE).status_code == 403
    creado = client.post(TIPOS, json=BODY, headers=ADMIN).json()["datos"]
    url = f'{TIPOS}/{creado["tipoAveriaId"]}'
    assert client.put(url, json=BODY, headers=CLIENTE).status_code == 403
    assert client.delete(url, headers=CLIENTE).status_code == 403


def test_actualizar_tipo_existente_y_404(client):
    creado = client.post(TIPOS, json=BODY, headers=ADMIN).json()["datos"]
    url = f'{TIPOS}/{creado["tipoAveriaId"]}'
    actualizado = client.put(url, json={**BODY, "nombre": "Fuga de aceite motor"}, headers=ADMIN)
    assert actualizado.status_code == 200
    assert actualizado.json()["datos"]["nombre"] == "Fuga de aceite motor"
    assert client.put(f"{TIPOS}/ave_no_existe", json=BODY, headers=ADMIN).status_code == 404


def test_validacion_de_campos_y_json_mal_formado(client):
    assert client.post(TIPOS, json={**BODY, "codigo": "!"}, headers=ADMIN).status_code == 422
    respuesta = client.post(
        TIPOS, content="{mal json", headers={**ADMIN, "Content-Type": "application/json"}
    )
    assert respuesta.status_code == 400


def test_delete_falla_cerrado_si_mod05_no_puede_verificar_dependencias(client):
    creado = client.post(TIPOS, json=BODY, headers=ADMIN).json()["datos"]
    respuesta = client.delete(f'{TIPOS}/{creado["tipoAveriaId"]}', headers=ADMIN)
    assert respuesta.status_code == 503


def test_delete_devuelve_409_si_tipo_esta_en_uso(client):
    class EnUso:
        def esta_en_uso(self, tipo_averia_id):
            return True

    app.dependency_overrides[get_uso_tipo_averia] = lambda: EnUso()
    creado = client.post(TIPOS, json=BODY, headers=ADMIN).json()["datos"]
    respuesta = client.delete(f'{TIPOS}/{creado["tipoAveriaId"]}', headers=ADMIN)
    assert respuesta.status_code == 409


def test_delete_permite_tipo_si_mod05_confirma_que_no_esta_en_uso(client):
    class SinUso:
        def esta_en_uso(self, tipo_averia_id):
            return False

    app.dependency_overrides[get_uso_tipo_averia] = lambda: SinUso()
    creado = client.post(TIPOS, json=BODY, headers=ADMIN).json()["datos"]
    respuesta = client.delete(f'{TIPOS}/{creado["tipoAveriaId"]}', headers=ADMIN)
    assert respuesta.status_code == 200


def test_reglas_fijas_se_consultan_como_no_editables(client):
    respuesta = client.get(REGLAS, headers=CLIENTE)
    assert respuesta.status_code == 200
    reglas = respuesta.json()["datos"]["reglasAuxilio"]
    assert len(reglas) == 2
    assert all(regla["editable"] is False for regla in reglas)
    valores = {regla["codigo"]: regla["valor"] for regla in reglas}
    assert valores["UBICACION_ANTIGUEDAD_MAX_MIN"] == 2
    assert valores["VENTANA_CALIFICACION_HORAS"] == 48


def test_no_se_puede_modificar_invariante_del_dominio(client):
    regla = client.get(REGLAS, headers=CLIENTE).json()["datos"]["reglasAuxilio"][0]
    respuesta = client.put(f'{REGLAS}/{regla["reglaId"]}', json={"valor": 99}, headers=ADMIN)
    assert respuesta.status_code == 422


def test_regla_configurable_se_actualiza_y_se_expone(client):
    from app.core.database import get_db

    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        db.add(ReglaAuxilioModel(
            id="radio_busqueda_km", codigo="RADIO_BUSQUEDA_KM", nombre="Radio de búsqueda",
            descripcion="Radio operativo configurable", valor=15, editable=True,
        ))
        db.commit()
    finally:
        try:
            next(generator)
        except StopIteration:
            pass

    respuesta = client.put(
        f"{REGLAS}/radio_busqueda_km", json={"valor": 25}, headers=ADMIN
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["valor"] == 25
    consulta = client.get(REGLAS, headers=CLIENTE).json()["datos"]["reglasAuxilio"]
    assert next(r for r in consulta if r["reglaId"] == "radio_busqueda_km")["valor"] == 25


def test_usuario_no_admin_no_actualiza_reglas(client):
    regla = client.get(REGLAS, headers=CLIENTE).json()["datos"]["reglasAuxilio"][0]
    assert client.put(f'{REGLAS}/{regla["reglaId"]}', json={"valor": 7}, headers=CLIENTE).status_code == 403


def test_regla_inexistente_devuelve_404(client):
    assert client.put(f"{REGLAS}/no_existe", json={"valor": 1}, headers=ADMIN).status_code == 404
