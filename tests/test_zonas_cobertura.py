import datetime as d

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from main import app

URL = "/api/v1/parametros/zonas-cobertura"


def _token(rol="ADMINISTRADOR"):
    payload = {
        "sub": "usr_test",
        "rol": rol,
        "exp": d.datetime.now(d.timezone.utc) + d.timedelta(hours=1),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _headers(rol="ADMINISTRADOR"):
    return {"Authorization": f"Bearer {_token(rol)}"}


def _datos(nombre="Bucaramanga", **cambios):
    return {
        "nombre": nombre,
        "latitudCentro": 7.1193,
        "longitudCentro": -73.1227,
        "radioKm": 10,
        "activa": True,
        **cambios,
    }


def _crear_zona(client, nombre="Bucaramanga", **cambios):
    datos = {**_datos(nombre), **cambios}
    return client.post(URL, json=datos, headers=_headers())


def _codigo_error(respuesta):
    return respuesta.json()["datos"]["errores"][0]["codigo"]


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_listar_zonas(client):
    _crear_zona(client)

    respuesta = client.get(URL, headers=_headers("CLIENTE"))

    assert respuesta.status_code == 200
    assert len(respuesta.json()["datos"]["zonas"]) == 1


def test_listar_zonas_sin_datos(client):
    respuesta = client.get(URL, headers=_headers("CLIENTE"))

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["zonas"] == []


def test_filtrar_zonas_por_estado_activa(client):
    activa = _crear_zona(client, nombre="Activa").json()["datos"]
    inactiva = _crear_zona(client, nombre="Inactiva", activa=False).json()["datos"]

    activas = client.get(URL, params={"activa": "true"}, headers=_headers())
    inactivas = client.get(URL, params={"activa": "false"}, headers=_headers())

    assert [z["zonaId"] for z in activas.json()["datos"]["zonas"]] == [activa["zonaId"]]
    assert [z["zonaId"] for z in inactivas.json()["datos"]["zonas"]] == [inactiva["zonaId"]]


def test_consultar_una_zona(client):
    zona = _crear_zona(client).json()["datos"]

    respuesta = client.get(f"{URL}/{zona['zonaId']}", headers=_headers("CLIENTE"))

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"] == zona


def test_zona_inexistente_404_mensaje_exacto(client):
    respuesta = client.get(f"{URL}/zon_999", headers=_headers("CLIENTE"))

    assert respuesta.status_code == 404
    assert respuesta.json()["mensaje"] == "Recurso no encontrado"


def test_configuracion_valida_persiste_centro_y_radio(client):
    datos = _datos()

    respuesta = client.post(URL, json=datos, headers=_headers())

    assert respuesta.status_code == 201
    assert {k: respuesta.json()["datos"][k] for k in datos} == datos


def test_radio_negativo_fuera_de_rango_no_crea_zona(client):
    respuesta = client.post(URL, json=_datos(radioKm=-1), headers=_headers())

    assert respuesta.status_code == 422
    assert _codigo_error(respuesta) == "FUERA_DE_RANGO"
    assert client.get(URL, headers=_headers()).json()["datos"]["zonas"] == []


def test_nombre_ausente_es_obligatorio(client):
    datos = _datos()
    del datos["nombre"]

    respuesta = client.post(URL, json=datos, headers=_headers())

    assert respuesta.status_code == 422
    assert _codigo_error(respuesta) == "CAMPO_OBLIGATORIO"
    assert client.get(URL, headers=_headers()).json()["datos"]["zonas"] == []


def test_latitud_centro_fuera_de_rango(client):
    respuesta = client.post(URL, json=_datos(latitudCentro=95), headers=_headers())

    assert respuesta.status_code == 422
    assert _codigo_error(respuesta) == "FUERA_DE_RANGO"


def test_longitud_centro_fuera_de_rango(client):
    respuesta = client.post(URL, json=_datos(longitudCentro=181), headers=_headers())

    assert respuesta.status_code == 422
    assert _codigo_error(respuesta) == "FUERA_DE_RANGO"


def test_longitud_centro_ausente_es_obligatoria(client):
    datos = _datos()
    del datos["longitudCentro"]

    respuesta = client.post(URL, json=datos, headers=_headers())

    assert respuesta.status_code == 422
    assert _codigo_error(respuesta) == "CAMPO_OBLIGATORIO"


def test_nombre_duplicado_409_con_codigo(client):
    _crear_zona(client)

    respuesta = _crear_zona(client)

    assert respuesta.status_code == 409
    assert respuesta.json()["datos"] == {"codigo": "ZONA_DUPLICADA"}
    assert len(client.get(URL, headers=_headers()).json()["datos"]["zonas"]) == 1


def test_actualizar_zona_reemplaza_los_cinco_campos(client):
    zona = _crear_zona(client).json()["datos"]
    datos = {
        "nombre": "Bucaramanga actualizada",
        "latitudCentro": 8,
        "longitudCentro": -74,
        "radioKm": 15,
        "activa": False,
    }

    respuesta = client.put(f"{URL}/{zona['zonaId']}", json=datos, headers=_headers())

    assert respuesta.status_code == 200
    assert {k: respuesta.json()["datos"][k] for k in datos} == datos
    assert respuesta.json()["datos"]["zonaId"] == zona["zonaId"]


def test_actualizar_zona_exige_los_cinco_campos(client):
    zona = _crear_zona(client).json()["datos"]
    datos = _datos()
    del datos["activa"]

    respuesta = client.put(f"{URL}/{zona['zonaId']}", json=datos, headers=_headers())

    assert respuesta.status_code == 422
    assert _codigo_error(respuesta) == "CAMPO_OBLIGATORIO"
    actual = client.get(f"{URL}/{zona['zonaId']}", headers=_headers()).json()["datos"]
    assert actual == zona


def test_actualizar_zona_inexistente_404_mensaje_exacto(client):
    respuesta = client.put(f"{URL}/zon_999", json=_datos(), headers=_headers())

    assert respuesta.status_code == 404
    assert respuesta.json()["mensaje"] == "Recurso no encontrado"


def test_actualizar_con_nombre_duplicado_409_con_codigo(client):
    _crear_zona(client, nombre="Primera")
    segunda = _crear_zona(client, nombre="Segunda").json()["datos"]

    respuesta = client.put(
        f"{URL}/{segunda['zonaId']}",
        json=_datos("Primera"),
        headers=_headers(),
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["datos"] == {"codigo": "ZONA_DUPLICADA"}
    assert client.get(f"{URL}/{segunda['zonaId']}", headers=_headers()).json()["datos"]["nombre"] == "Segunda"


def test_rol_no_administrador_no_crea_zona(client):
    respuesta = client.post(URL, json=_datos(), headers=_headers("CLIENTE"))

    assert respuesta.status_code == 403
    assert client.get(URL, headers=_headers()).json()["datos"]["zonas"] == []


def test_token_ausente_no_crea_zona(client):
    respuesta = client.post(URL, json=_datos())

    assert respuesta.status_code == 401
    assert client.get(URL, headers=_headers()).json()["datos"]["zonas"] == []


def test_json_mal_formado_no_crea_zona(client):
    respuesta = client.post(
        URL,
        content='{"nombre":',
        headers={**_headers(), "Content-Type": "application/json"},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["mensaje"] == "Solicitud mal formada"
    assert client.get(URL, headers=_headers()).json()["datos"]["zonas"] == []


def test_eliminar_zona_sin_dependencias(client):
    zona = _crear_zona(client).json()["datos"]

    respuesta = client.delete(f"{URL}/{zona['zonaId']}", headers=_headers())

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"] == {"zonaId": zona["zonaId"]}
    consulta = client.get(f"{URL}/{zona['zonaId']}", headers=_headers())
    assert consulta.status_code == 404
    assert consulta.json()["mensaje"] == "Recurso no encontrado"


def test_eliminar_zona_sin_rol_administrador_la_conserva(client):
    zona = _crear_zona(client).json()["datos"]

    respuesta = client.delete(f"{URL}/{zona['zonaId']}", headers=_headers("CLIENTE"))

    assert respuesta.status_code == 403
    consulta = client.get(f"{URL}/{zona['zonaId']}", headers=_headers())
    assert consulta.status_code == 200
    assert consulta.json()["datos"] == zona
